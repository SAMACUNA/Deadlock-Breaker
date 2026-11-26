import sys

from algorithms import demo, run_test_report, to_plain
from gui import App, tk


def main():
    if "--test" in sys.argv:
        lines, ok = run_test_report()
        print(to_plain(lines))
        sys.exit(0 if ok else 1)
    if "--demo" in sys.argv:
        demo()
        return
    if tk is None:
        print("tkinter is not installed. Install it (Linux: sudo apt install "
              "python3-tk) or use --test / --demo.")
        return
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
