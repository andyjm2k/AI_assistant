"""CLI entrypoint for CATBot GitHub integration module."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .service import GitHubIntegrationService


def _print_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="catbot-github",
        description="Source control and version management helper for CATBot.",
    )
    parser.add_argument(
        "--workspace",
        default=".",
        help="Repository path to manage (default: current directory).",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Initialize git repository and VERSION file.")
    init_parser.add_argument("--remote-url", help="Optional remote URL to set for origin.")

    subparsers.add_parser("status", help="Show git and version status.")

    fetch_parser = subparsers.add_parser("fetch", help="Fetch from remote.")
    fetch_parser.add_argument("--remote", help="Remote name (defaults to configured remote).")

    pull_parser = subparsers.add_parser("pull", help="Pull from remote.")
    pull_parser.add_argument("--remote", help="Remote name (defaults to configured remote).")
    pull_parser.add_argument("--branch", help="Branch to pull from.")
    pull_parser.add_argument("--rebase", action="store_true", help="Use rebase when pulling.")

    push_parser = subparsers.add_parser("push", help="Push to remote.")
    push_parser.add_argument("--remote", help="Remote name (defaults to configured remote).")
    push_parser.add_argument("--branch", help="Branch to push (defaults to current branch).")
    push_parser.add_argument("--set-upstream", action="store_true", help="Set upstream tracking.")
    push_parser.add_argument("--tags", action="store_true", help="Push tags along with branch.")

    sync_parser = subparsers.add_parser("sync", help="Pull then push.")
    sync_parser.add_argument("--remote", help="Remote name (defaults to configured remote).")
    sync_parser.add_argument("--branch", help="Branch to sync (defaults to current branch).")
    sync_parser.add_argument("--rebase", action="store_true", help="Use rebase for pull step.")
    sync_parser.add_argument("--set-upstream", action="store_true", help="Set upstream during push.")
    sync_parser.add_argument("--tags", action="store_true", help="Push tags during sync.")

    branch_parser = subparsers.add_parser("branch", help="Create and checkout a new branch.")
    branch_parser.add_argument("name", help="New branch name.")
    branch_parser.add_argument("--from-ref", help="Base ref to branch from.")
    branch_parser.add_argument("--push", action="store_true", help="Push created branch.")
    branch_parser.add_argument("--set-upstream", action="store_true", help="Set upstream when pushing.")
    branch_parser.add_argument("--remote", help="Remote name (defaults to configured remote).")

    checkout_parser = subparsers.add_parser("checkout", help="Checkout an existing branch.")
    checkout_parser.add_argument("name", help="Branch name.")

    repo_parser = subparsers.add_parser("repo", help="Show GitHub repository metadata.")
    repo_parser.add_argument("--include-rate-limit", action="store_true", help="Include current API core rate limit.")

    bump_parser = subparsers.add_parser("bump", help="Bump semantic version only.")
    bump_parser.add_argument("level", choices=["major", "minor", "patch"])

    commit_parser = subparsers.add_parser("commit", help="Bump version, commit changes, and tag.")
    commit_parser.add_argument("--message", required=True, help="Commit message prefix.")
    commit_parser.add_argument("--bump", choices=["major", "minor", "patch"], default="patch")
    commit_parser.add_argument("--tag-prefix", default="v")
    commit_parser.add_argument("--push", action="store_true", help="Push commit and tags to remote.")

    pr_parser = subparsers.add_parser("pr", help="Create a pull request via GitHub API.")
    pr_parser.add_argument("--title", required=True)
    pr_parser.add_argument("--head", required=True)
    pr_parser.add_argument("--base")
    pr_parser.add_argument("--body", default="")

    list_prs_parser = subparsers.add_parser("prs", help="List pull requests from GitHub.")
    list_prs_parser.add_argument("--state", choices=["open", "closed", "all"], default="open")
    list_prs_parser.add_argument("--sort", default="created")
    list_prs_parser.add_argument("--direction", default="desc")
    list_prs_parser.add_argument("--per-page", type=int, default=30)
    list_prs_parser.add_argument("--page", type=int, default=1)

    release_parser = subparsers.add_parser("release", help="Create versioned commit + GitHub release.")
    release_parser.add_argument("--title")
    release_parser.add_argument("--notes", default="")
    release_parser.add_argument("--bump", choices=["major", "minor", "patch"], default="patch")
    release_parser.add_argument("--prerelease", action="store_true")
    release_parser.add_argument(
        "--no-push",
        action="store_true",
        help="Do not push commit and tags before creating release.",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    service = GitHubIntegrationService.from_env(Path(args.workspace))

    if args.command == "init":
        _print_json(service.initialize_repository(remote_url=args.remote_url))
        return
    if args.command == "status":
        _print_json(service.status())
        return
    if args.command == "fetch":
        _print_json(service.fetch(remote_name=args.remote))
        return
    if args.command == "pull":
        _print_json(
            service.pull(
                remote_name=args.remote,
                branch=args.branch,
                rebase=args.rebase,
            )
        )
        return
    if args.command == "push":
        _print_json(
            service.push(
                remote_name=args.remote,
                branch=args.branch,
                set_upstream=args.set_upstream,
                tags=args.tags,
            )
        )
        return
    if args.command == "sync":
        _print_json(
            service.sync(
                remote_name=args.remote,
                branch=args.branch,
                rebase=args.rebase,
                set_upstream=args.set_upstream,
                tags=args.tags,
            )
        )
        return
    if args.command == "branch":
        _print_json(
            service.create_branch(
                args.name,
                from_ref=args.from_ref,
                push=args.push,
                set_upstream=args.set_upstream,
                remote_name=args.remote,
            )
        )
        return
    if args.command == "checkout":
        _print_json(service.checkout_branch(args.name))
        return
    if args.command == "repo":
        _print_json(service.repository_info(include_rate_limit=args.include_rate_limit))
        return
    if args.command == "bump":
        _print_json(service.bump_version(args.level))
        return
    if args.command == "commit":
        result = service.commit_versioned_change(
            message=args.message,
            bump=args.bump,
            tag_prefix=args.tag_prefix,
            push=args.push,
        )
        _print_json(
            {
                "commit": result.commit.commit_hash,
                "branch": result.commit.branch,
                "tag": result.tag,
                "previous_version": result.version.previous,
                "current_version": result.version.current,
            }
        )
        return
    if args.command == "pr":
        _print_json(service.create_pull_request(args.title, args.head, body=args.body, base=args.base))
        return
    if args.command == "prs":
        _print_json(
            service.list_pull_requests(
                state=args.state,
                sort=args.sort,
                direction=args.direction,
                per_page=args.per_page,
                page=args.page,
            )
        )
        return
    if args.command == "release":
        _print_json(
            service.publish_release(
                title=args.title,
                notes=args.notes,
                bump=args.bump,
                prerelease=args.prerelease,
                push=not args.no_push,
            )
        )
        return

    parser.error(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
