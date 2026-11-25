---
name: fork-sync
description: Safely sync the HOBL fork with microsoft/HOBL hobl_27 using a linear rebase and an explicitly leased push.
---

# HOBL fork sync

Synchronize the current development branch with `microsoft/HOBL` branch
`hobl_27`, preserving local work and maintaining linear history above upstream.
Follow the repository's Copilot instructions. Use Windows PowerShell commands.

## Safety boundaries

- Inspect the current branch, worktree, remotes, and stash before changing state.
- Verify `upstream` points to `https://github.com/microsoft/HOBL.git` and the
  push URL for `origin` points to `https://github.com/a5hut05h/HOBL_MINCP.git`.
  Stop and ask if either differs; do not silently reconfigure remotes.
- Never push to `upstream`, use plain `--force`, or discard local changes.
- A fetch-only request authorizes no merge, rebase, or push.
- Rebase only when integration is requested. Push only when explicitly requested.
- Do not commit unrelated work or include untracked files in a sync commit.
- Do not edit generated Scenarios or Tools documentation during synchronization.

## Workflow

1. Fetch `hobl_27` from `upstream`, then report the upstream tip and divergence.
   Use `git fetch upstream hobl_27`.
2. Before integration, record the starting commit and create a uniquely named
   backup branch. If the worktree is dirty, stash tracked and untracked changes
   with `git stash push --include-untracked` and record the exact stash object ID.
   Leave ignored content untouched. Stop if preservation fails.
3. Use a fast-forward when possible. Otherwise rebase onto `upstream/hobl_27`
   for linear history. Explain that this rewrites published commit IDs. If local
   merge commits exist, explain that a linear rebase flattens them before proceeding.
4. Resolve conflicts by inspecting the incoming changes and the replayed commit's
   intent. Preserve both intended behaviors; never blindly select ours/theirs or
   skip commits to bypass conflicts. Ask when behavior is ambiguous.
5. Verify upstream is an ancestor of HEAD and there are no merge commits in
   `upstream/hobl_27..HEAD`. Review the final tree against the backup and validate
   affected Python/JSON syntax and relevant tests. Do not run DUT workloads
   merely to synchronize Git history.
6. Restore the exact recorded stash, verify all preserved work is restored, and
   only then drop that specific stash entry. Do not drop a stash on conflict or
   failed verification. Retain the backup branch.
7. If a push was requested, fetch the exact destination branch into its
   remote-tracking ref. Do not rely on plain `git fetch origin`: this repository
   may have a restricted fetch mapping. A rewritten remote-tracking ref may
   require an explicit `+` refspec; this changes only the local tracking ref.
8. Before replacing remote history, verify the freshly fetched fork tip is
   included in the pre-rebase backup. If it is not, stop to inspect new remote
   commits; do not overwrite them. Record the fetched tip as the lease value.
9. Push only the requested branch. For rewritten history use an explicit lease:

   ```powershell
   git push "--force-with-lease=refs/heads/${branch}:$expected" origin "HEAD:refs/heads/$branch"
   ```

   Obtain `$branch` and `$expected` from verified Git output, not assumed values.
   Never retry a rejected lease without reviewing the remote changes.
10. Use `git ls-remote --heads origin` for the exact destination branch and verify
    its SHA matches local HEAD after pushing.

## Completion report

Report the upstream commit, integration result, conflicts and resolutions,
validation results, restored work, backup branch, and whether a push occurred.
If blocked, report the exact rebase/stash state and safe next steps. Never claim
that a fetch updated working files or that a successful rebase proves DUT behavior.
