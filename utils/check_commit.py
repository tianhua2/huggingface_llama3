import argparse
import re
import subprocess


def create_script(target_test):

    script = f"""
import os
import subprocess



result = subprocess.run(
    ["python3", "-m", "pytest", "-v", f"{target_test}"],
    capture_output = True,
    text=True,
)
print(result.stdout)

if f"{target_test} FAILED" in result.stdout:
    print("failed")
    exit(2)

exit(0)
"""

    with open("target_script.py", "w") as fp:
        fp.write(script.strip())


def find_bad_commit(target_test, start_commit, end_commit):

    create_script(target_test=target_test)

    bash = f"""
git bisect reset
git bisect start {start_commit} {end_commit}
git bisect run python3 target_script.py
"""

    with open("run_git_bisect.sh", "w") as fp:
        fp.write(bash.strip())

    result = subprocess.run(
        ["bash", "run_git_bisect.sh"],
        capture_output = True,
        text=True,
    )
    print(result.stdout)

    pattern = r"(.+) is the first bad commit"
    commits = re.findall(pattern, result.stdout)

    bad_commit = None
    if len(commits) > 0:
        bad_commit = commits[0]

    print(f"Between `start_commit` {start_commit} and `end_commit` {end_commit}")
    print(f"bad_commit: {bad_commit}\n")

    return bad_commit


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start_commit", type=str, required=True, help="The starting commit hash.")
    parser.add_argument("--end_commit", type=str, required=True, help="The ending commit hash.")
    args = parser.parse_args()

    print(args.start_commit)
    print(args.end_commit)

    target_test = "tests/models/vit/test_modeling_vit.py::ViTModelTest::test_foo"
    find_bad_commit(target_test=target_test, start_commit=args.start_commit, end_commit=args.end_commit)

    # python3 check_commit2.py --start_commit 54705c8a --end_commit 317e069e
