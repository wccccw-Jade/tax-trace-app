# Backup and restore

Back up PostgreSQL and all referenced private attachments together. Pause application writes while capturing a backup. The command checks the database before/after and aborts if table contents changed; do not treat a partial directory as a completed backup.

## Create a backup

```sh
make backup
```

This writes an ignored, private directory under `var/backups/` containing a custom-format PostgreSQL dump, referenced attachment bytes and a checksum/table manifest. It reads from the configured local or S3 attachment adapter. Database passwords are passed through the child environment, not command arguments or console output. The script uses native PostgreSQL tools when available, otherwise PostgreSQL 17 tools in the running Docker Compose container.

The backup contains private application records and sessions. Keep it in protected backup storage; do not commit or publish it. The backup includes attachments referenced by the database, not unrelated/orphaned objects elsewhere in a bucket.

## Restore deliberately to an empty database

Create a separate empty PostgreSQL database first, and set its connection in `RESTORE_DATABASE_URL`. Do not point it at the live database.

```sh
.venv/bin/python -m scripts.backup restore \
  --directory var/backups/YOUR_BACKUP \
  --database-env RESTORE_DATABASE_URL \
  --attachment-dir var/restored-attachments
```

The restore command verifies the dump/file checksums before restoring, refuses existing public tables and a nonempty attachment directory, restores without ownership/privilege changes, then compares table hashes. It never drops or cleans an existing target. If a restore fails partway, investigate and use another empty target; the script will not overwrite the partial target on retry.

For a hosted recovery, stop writes, restore Postgres to the intended new database, and copy the verified attachment bytes to the configured private bucket prefix with the **same keys** used in the manifest. The current restore command materializes local files; it does not silently upload or re-key cloud objects. Switch configuration only after the app can read the restored records/files and their checksums agree. Check the PostgreSQL client version is compatible with the source server.

## Reproduce the local drill

```sh
make backup-drill
```

The automated drill is restricted to local PostgreSQL:

1. Capture the live database/attachments without modifying them.
2. Restore to a disposable clone.
3. Add a clearly synthetic attachment, revision-7 record and frozen snapshot **only in that clone**.
4. Back up the clone and restore to a second disposable database/directory.
5. Verify all table hashes, attachment bytes, saved revision and rejection of a snapshot update.
6. Drop only the two generated disposable databases. Keep the result JSON and backup manifests under the ignored drill directory.

The Day 9 drill passed: **11 tables**, **one synthetic attachment**, revision preservation and immutable-snapshot protection. The live database was unchanged. See `var/backups/day9-restore-drill/result.json` for the local execution record. This is a local recovery result, not proof that a remote bucket or Heroku backup has been tested.
