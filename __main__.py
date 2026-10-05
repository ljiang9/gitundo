"""gitundo package entry: python -m gitundo"""

try:
    from .gitundo import main
except ImportError:  # namespace-package fallback: python -m gitundo from its own dir
    from gitundo import main

if __name__ == "__main__":
    main()
