import sys


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] in ("-v", "--version"):
        print("AICONNEX Industrial Excel Compiler v0.1.0 (Phase 0 Baseline)")
        sys.exit(0)
    elif args[0] == "health":
        print("System status: healthy (Phase 0 scaffold ready)")
        sys.exit(0)
    else:
        print(f"Unknown command: {' '.join(args)}")
        print("Usage: compiler [--version | health]")
        sys.exit(1)


if __name__ == "__main__":
    main()
