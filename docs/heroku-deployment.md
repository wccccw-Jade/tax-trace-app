# Heroku deployment runbook

The repository is prepared for a **Cedar-generation Heroku app with classic Node.js then Python buildpacks**. The frontend and API share one origin. Python 3.15 and Node 24 are declared; the `release` process applies Alembic migrations and imports the unchanged packet idempotently. No app or paid add-on has been created by this work.

## Inputs still needed

- Target Heroku app, authenticated Heroku access, and its Postgres attachment.
- A private S3-compatible bucket, region and optional endpoint, plus credentials configured through the platform secret store.
- Bucket public access must be blocked. The app needs object read/write/delete only under `S3_PREFIX`; it does not return public object URLs. Keep bucket retention/versioning appropriate to the case study.

The Heroku CLI is not installed in the current workspace. No cloud credentials were found in the task environment. Actual release, hosted role switching, bucket connectivity and hosted restart/redeployment checks remain pending.

## Configure the existing app

After the target is identified, use the Heroku CLI or dashboard to configure it. Replace `YOUR_APP` with the real app name. Do not print credentials or commit them to Git.

```sh
heroku buildpacks:set heroku/nodejs --app YOUR_APP
heroku buildpacks:add heroku/python --app YOUR_APP
heroku git:remote --app YOUR_APP
```

Attach Heroku Postgres using the selected plan in the dashboard, and verify it supplies `DATABASE_URL`. The code accepts `postgres://` and `postgresql://`, selects psycopg 3 and requires database SSL in production.

Configure these values in the app's config vars:

| Variable | Value |
| --- | --- |
| `APP_ENV` | `production` |
| `ATTACHMENT_BACKEND` | `s3` |
| `S3_BUCKET` | The private bucket name |
| `S3_REGION` | The bucket region |
| `S3_ENDPOINT_URL` | Omit for AWS; set for another S3-compatible service |
| `S3_PREFIX` | A dedicated prefix, e.g. `miraflores/attachments/` |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | Platform-managed credentials; optional session token when applicable |

Production startup rejects local attachment storage so files cannot silently disappear on a dyno restart. Secure, HTTP-only demo cookies are used in production. The role switcher remains a demonstration identity mechanism for invented data, not production authentication.

## Build, release and verify

Push the reviewed commit to the selected app:

```sh
git push heroku HEAD:main
heroku releases --app YOUR_APP
heroku logs --tail --app YOUR_APP
```

The root `heroku-postbuild` script installs the locked frontend dependencies and builds Vite. The Python release command runs migrations and idempotent import. `Procfile` binds Uvicorn to `$PORT`.

Verify `https://YOUR_APP.herokuapp.com/api/health` and `/api/ready`, then:

1. Select Priya, inspect a claim/source and record a legitimate review action or a clearly identified deployment-check task assignment. Record the returned revision.
2. Use an assigned client thread to upload an invented attachment. Confirm only its owner or cleared staff can download it and its hash agrees. Uncleared staff must not get the original file.
3. Switch roles and verify clients cannot open internal views, and uncleared staff see masked identifiers.
4. Restart the app, reopen the same saved record and attachment, and verify their revision/hash and frozen-copy hashes.
5. Redeploy the same reviewed code and repeat the persistence checks. Packet import must remain idempotent and prior records must remain.
6. Confirm no real filing, signature or payment is implied. Report the actual app link and evidence of these checks before marking deployment complete.

Do not use dyno disk for attachment persistence. Existing local attachments must be copied to the bucket under the **same storage keys** and verified before switching a workspace with attachments to S3. A fresh cloud import does not automatically migrate local review history; restore an intentional database/attachment backup if that history should be carried forward.

## Sources

The buildpack order follows [Heroku's multi-buildpack guidance](https://devcenter.heroku.com/articles/managing-buildpacks). The migration/import hook follows [Heroku release phase](https://devcenter.heroku.com/articles/release-phase), and the runtime declaration follows [Python version selection](https://devcenter.heroku.com/articles/python-runtimes). S3 requests omit ACLs and public URLs, consistent with [boto3 object upload behavior](https://docs.aws.amazon.com/boto3/latest/reference/services/s3/bucket/put_object.html). Bucket public-access policy must still be verified on the actual service.
