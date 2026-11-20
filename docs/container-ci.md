# Container validation and cache trust

Pull requests build the actual shipped Dockerfile runtime targets on native
`linux/amd64`, without publishing an application image or deploying. Runtime
checks inspect the revision label and confirm that Git metadata is absent.
Release builds still rebuild the release commit and stamp its full SHA; they do
not promote a PR image or reuse its revision identity.

## Safe cache fallback

BuildKit uses GitHub Actions (`type=gha`) caches for repeat PR builds and
base-branch reuse. GitHub restricts PR-written caches to that PR's merge ref;
a release cannot restore those PR caches. Each image has a separate cache scope.
Registry caches are written only by the existing release job. PR jobs receive
no registry login and have only `contents: read` repository-token permission.
A missing cache is a cold build, not a reason to skip image validation.

This is **not PR-to-release cache promotion**. A registry tag such as
`buildcache-pr-123` is a naming convention, not an authorization boundary: a
repository-wide package-write credential would still permit overwriting trusted
release caches. Until an isolated cache-only exporter/credential is available,
we deliberately keep those credentials out of PR jobs. No repository, runner,
registry, or branch-protection settings are changed by this workflow.

The release cache speeds subsequent trusted release builds and PR builds can
read the base-branch GHA cache where available. No unreviewed PR cache is used as
trusted input to a release. Application-image publication and deployment stay
in the release workflow, not the premerge checks.
