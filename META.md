# poor man's series

This repo is part of the **poor man's** series — small, single-purpose,
self-contained replacements for tools that have become industry-default
when most of us just wanted `ssh` to do the work.

## Other entries

- **poor man's CI** — cron + a bash script + a wiki page
- **poor man's queue** — `at(1)` + a shared `/var/spool/at/` (this repo)
- **poor man's service mesh** — `ssh -J` + `ProxyCommand`
- **poor man's secret manager** — `pass(1)` + a GPG key
- **poor man's monitoring** — `watch -n 5 'curl localhost:8080/health'`
- **poor man's feature flags** — a file in `~/`

## Why this exists

Software has a tendency to grow. The poor man's series is a reminder that
**most of the time, a small bash script and a 200-line Python file
solve the problem just as well as a 12-container microservices stack** —
and are easier to debug, easier to delete, and easier to reason about
in 5 years.

## License

MIT.
