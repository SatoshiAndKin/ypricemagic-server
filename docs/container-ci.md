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

## Python runtime qualification

A Python runtime change must pass a full application startup before merge. The
Python 3.14 images from [PR #206](https://github.com/SatoshiAndKin/ypricemagic-server/pull/206)
passed build checks but failed production health. [PR #207](https://github.com/SatoshiAndKin/ypricemagic-server/pull/207)
restored the verified Python 3.12 runtime. The isolated recovery fixture reached
an explorer ABI lookup but could not qualify readiness.

1. Record the baseline and candidate commits, image digests, interpreter versions,
   and installed native-extension origins. Build the actual Dockerfile runtime
   target with each commit as its Sentry release. Use the locked build tools.
2. Start each image through its normal entrypoint with a separate network identity
   and fresh private cache directories. Use the approved Ethereum test RPC and
   explorer credentials through protected environment references. Keep the test
   instance outside production Service selectors and set an empty Sentry DSN.
3. Exercise Brownie network registration, dank-mids initialization, required
   registry prewarming, and the real application lifespan. Record container exit
   status and startup failures. A compile or import check does not complete this step.
4. Require HTTP 200 from the API health route, status `ok`, Ethereum chain identity,
   and a synced block. Verify that the process retains its expected release ID
   and stays healthy after initialization.
5. Request current USDC and WETH prices and a pinned historical USDC price. Use
   the same block and amounts for both images. Require finite positive prices,
   a USDC price within 2% of USD 1, and baseline/candidate agreement within 2%
   for USDC and 10% for WETH. Check the response token and block identity.
6. Retain the image identities, health and price responses, and sanitized failure
   details in the task record. If either image fails initialization or a comparison,
   diagnose the failure before qualifying the runtime. Then stop and remove only
   the owned test instance and its disposable caches.

After deployment, correlate the release workflow with its successful controller
receipt, Ready container image IDs, full-SHA Sentry release, and the same health
and pricing checks. Keep the prior verified image available for controller rollback.
