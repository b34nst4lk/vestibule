# Research: How apps manage environment secrets / uncommitted config files

**Question:** How do other applications manage environment secrets — setting them into a
`.env` file (or another config file that is not checked in) — and how do they handle the
"update just one of many secrets" case?

**Context:** Vestibule's `vestibule setup` wizard currently **regenerates the whole `.env`
file from plugin secret declarations**, reading "current" values only from `os.environ`.
If a user updates 1 of N secrets but the other N−1 live only in the existing `.env` (not
exported), regenerating the file can silently drop them. This note surveys how the
ecosystem handles this so we can pick a safe model.

---

## Key finding: there are two competing update models

The ecosystem's tools split into two camps:

1. **Regenerate the whole file** — safe *only* when a single authoritative source of
   truth (the environment, or a secrets manager) holds *all* values, so nothing is lost.
2. **Merge-safe targeted update** — read the existing file, rewrite *only the one line*
   for the changed key, preserve comments and every other key untouched.

For a `.env` editor there is no single source of truth (the file *is* the store), so the
**merge-safe targeted update is the established, correct primitive** for "change one of
many."

---

## 1. python-dotenv — the de facto standard, and the merge-safe primitive

Source: https://github.com/theskumar/python-dotenv (BSD-3, ~8.8k stars); source of
`set_key`/`unset_key`/`rewrite` in `src/dotenv/main.py`.

- Reading: `load_dotenv()` loads into the process env (`override=False` by default — does
  **not** clobber an existing env var); `dotenv_values()` returns a dict without touching
  the environment.
- **The critical API for our question is `set_key()` / `unset_key()`.** Their implementation
  is a **line-preserving rewrite** (see `main.py` `set_key`):

  ```python
  with rewrite(dotenv_path, ...) as (source, dest):
      replaced = False
      for mapping in with_warn_for_invalid_lines(parse_stream(source)):
          if mapping.key == key_to_set:
              dest.write(line_out)      # only this key's line is replaced
              replaced = True
          else:
              dest.write(mapping.original.string)   # every other line preserved verbatim
      if not replaced:
          dest.write(line_out)          # key not present -> append at end
  ```

  - It reads the whole file, rewrites the target key's line, writes **all other lines
    unchanged** (preserving comments and other keys), and **appends** the key if absent.
  - `rewrite()` (source) is atomic: writes to a temp file then `os.replace`, preserves the
    original file mode, and uses mode `0o600` when creating a new file.
  - CLI: `dotenv set KEY VALUE` / `dotenv unset KEY` expose the same per-key behavior.
- Changelog note: v0.8.0 "`set_key` and `unset_key` only modified the affected file instead
  of parsing and re-writing [the whole] file, this causes comments and other file [entries
  to remain] intact" — the community explicitly moved *toward* targeted updates to avoid
  clobbering comments/unrelated keys.

**Takeaway:** the canonical way to "update 1 of many" in a `.env` is a targeted line
rewrite, not a full-file regeneration.

---

## 2. Twelve-Factor: config lives in the environment; *how* you populate it is your choice

Sources: https://12factor.net/config ; https://blog.doismellburning.co.uk/twelve-factor-config-misunderstandings-and-advice/ ;
https://stackoverflow.com/questions/43444781/does-dotenv-contradict-the-twelve-factor-app

- 12-factor stores config in **environment variables**, and explicitly warns that config
  files which are not checked into version control (e.g. `config/database.yml` in Rails)
  are an improvement over hardcoding but have weaknesses: easy to check in accidentally,
  scattered, and language/framework-specific.
- The widely-cited clarification (Kristian Glass): *"12factor says your applications should
  read their config from the environment; it has very little to say about how you populate
  the environment — use whatever works for you."* So `.env` files, secret managers, shell
  env, etc. are all legitimate ways to *populate* the environment.
- Whether `.env` "violates" 12-factor is debated (a `.env` file is itself a config file),
  but it is a common, accepted dev convenience.

**Takeaway:** `.env` is a local dev convenience for populating the environment. In
production the values come from the deployment platform, not a file.

---

## 3. direnv — don't *edit* the file; *load* it per-directory

Sources: https://direnv.net ; https://github.com/direnv/direnv ; https://envtools.dev/compare/dotenv-vs-direnv

- direnv loads `.envrc` (bash) and optionally `.env` into your **shell** when you `cd`
  into a directory, and unloads on exit. It does not manage writing the file; it manages
  sourcing it.
- **Security feature dotenv lacks: allow-listing.** direnv refuses to load an `.envrc`
  until you run `direnv allow .`, which stops a malicious `git clone` from exporting
  attacker-controlled env vars into your shell.
- dotenv vs direnv: *dotenv loads `.env` into the app process at runtime (inside the app);
  direnv loads into your shell (outside the app). Many teams use both.* The common setup is
  an `.envrc` containing just `dotenv` plus a `.env` consumed by the app library.

**Takeaway:** another layer (shell-level loading) exists, but it doesn't solve writing/
updating `.env`; that still falls to the app or a tool.

---

## 4. Secret managers (Doppler) — cloud is the source of truth; `.env` is a derived output

Sources: https://docs.doppler.com/docs/setting-secrets ; https://docs.doppler.com/docs/accessing-secrets ;
https://docs.doppler.com/docs/secrets

- Doppler stores secrets centrally; per-secret writes use `doppler secrets set KEY` (the
  merge/update path is in the store, not a file).
- To produce a local `.env`, you *regenerate* it wholesale: `doppler secrets download
  --no-file --format env > .env`. This is safe **because Doppler is the single source of
  truth for every value** — regeneration cannot drop anything.
- Doppler recommends *against* keeping plaintext `.env` on disk at all: `doppler run
  --mount .env -- <cmd>` mounts secrets as an **ephemeral named pipe** (cleaned up on exit),
  and `--mount-max-reads 1` for one-shot readers.

**Takeaway:** full-file regeneration is only safe when a central store holds *all* values.
Without such a store (plain `.env`), regeneration is dangerous — which is exactly the
Vestibule footgun.

---

## 5. Framework conventions: `.env.example` committed + `.env*` gitignored

Sources: Laravel/Prisma/Next.js/Node docs:
- Prisma — https://www.prisma.io/docs/orm/more/dev-environment/environment-variables :
  *"Do not commit your `.env` files into version control!"*; `prisma init` creates a
  convenience `.env`; multiple env files supported; `.gitignore` generated includes `.env`.
- create-prisma — https://github.com/prisma/create-prisma : "creates or updates `.env` with
  `DATABASE_URL`" and writes a `.gitignore` with `.env`.
- Next.js — https://env.dev/guides/nextjs-env-variables : load order + precedence
  (`process.env` → `.env.{NODE_ENV}.local` → `.env.local` → `.env.{NODE_ENV}` → `.env`;
  first match wins); `.env.example` committed; `.env.local` gitignored; validate required
  vars at startup with a schema (Zod).
- Node built-in env-file — https://nodejs.org/api/environment_variables.html and
  https://www.thenodebook.com/runtime-platform/env-files-configuration : Node documents its
  own DotEnv grammar (v20.6 `--env-file`, v20.12 `process.loadEnvFile`/`util.parseEnv`);
  **parent environment wins over env-file values**; later env files override earlier ones;
  duplicate keys: last wins; `export` prefix accepted; `#` begins a comment in unquoted
  values; quoted values preserve `#`.
- Laravel setup wizards (e.g. LaravelDeployWizard — https://github.com/bijanbiria/LaravelDeployWizard):
  generate `.env` **from `.env.example` only when `.env` is missing** (auto-launch on first
  run); `APP_KEY` generation. Notably these are *first-run* generators, not per-secret
  updaters — they sidestep the merge problem by only running when there is nothing to merge.

**Takeaway:** the universal convention is: **commit a `.env.example` template, gitignore
`.env`/`.env.local`, and treat real values as local.** Framework setup wizards regenerate
whole files safely because they run on first boot when the file doesn't exist yet.

---

## Implications for Vestibule's `vestibule setup`

**Current behavior (regenerate-whole-file):** safe iff all values are in `os.environ`
when the wizard runs (Case A). Unsafe when values live only in the existing `.env` and
aren't exported (Case B) — updating 1 can silently drop the other N−1.

**Two ways to fix, both well-precedented:**

- **Option A (minimal, reuses existing code):** seed the wizard's "current value" baseline
  from the existing output file via `load_env_file()` as well as `os.getenv`. Then values
  already in `.env` are offered a "keep current?" prompt even when not exported, and
  `write_env_file` rewrites everything the user kept. Editing 1 secret preserves the rest.
  This is the pragmatic first step.
- **Option B (adopt the ecosystem's merge-safe primitive):** add a per-key updater that does
  python-dotenv-style **line-preserving rewrite** (replace only the target key's line,
  preserve comments + other keys, append if missing, atomic temp-file + `os.replace`,
  `0o600` on create). This matches `dotenv set` semantics exactly and is the long-term
  robust model. Could be exposed as `vestibule setup` update behavior or a
  `vestibule secrets set KEY` command.

**Security housekeeping the research surfaced (relevant to this repo):**
- The repo's `.gitignore` currently does **not** ignore `.env` or `.env.local` (only
  `.env.example` is tracked). Since `vestibule setup` writes secrets to `.env`, adding
  `.env`/`.env.local` to `.gitignore` closes an accidental-commit leak — matching the
  universal convention in §5.
- Consider committing a `.env.example` (already present) and documenting `chmod 600 .env`.

---

## Sources
- python-dotenv (README, `src/dotenv/main.py`, CHANGELOG): https://github.com/theskumar/python-dotenv
- Twelve-Factor Config: https://12factor.net/config
- "Twelve-Factor Config: Misunderstandings and Advice" (Kristian Glass): https://blog.doismellburning.co.uk/twelve-factor-config-misunderstandings-and-advice/
- dotenv vs 12-factor (StackOverflow): https://stackoverflow.com/questions/43444781/
- direnv (docs + README): https://direnv.net , https://github.com/direnv/direnv
- dotenv vs direnv (envtools): https://envtools.dev/compare/dotenv-vs-direnv
- Doppler docs: https://docs.doppler.com/docs/setting-secrets , /docs/accessing-secrets , /docs/secrets
- Prisma env-vars docs: https://www.prisma.io/docs/orm/more/dev-environment/environment-variables
- create-prisma: https://github.com/prisma/create-prisma
- Next.js env guide (env.dev): https://env.dev/guides/nextjs-env-variables
- Node env-file docs + grammar: https://nodejs.org/api/environment_variables.html , https://www.thenodebook.com/runtime-platform/env-files-configuration
- LaravelDeployWizard (first-run .env generator pattern): https://github.com/bijanbiria/LaravelDeployWizard
