import argparse
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

def find_bad_commit(target_test):

    create_script(target_test=target_test)

    result = subprocess.run(
        ["python3", "-m", "pytest", "-v", f"{target_test}"],
        capture_output = True,
        text=True,
    )


print(result.stdout)

    # git bisect start 317e069e 6d02968d

    # # if a test not exist: should be a good commit instead of bad commit
    # git bisect run "python3 target_script.py"

    # git bisect reset


    return commit



if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start_commit", type=str, required=True, help="The starting commit hash.")
    parser.add_argument("--end_commit", type=str, required=True, help="The ending commit hash.")
    args = parser.parse_args()

    print(args.start_commit)
    print(args.end_commit)


target_test = "tests/models/vit/test_modeling_vit.py::ViTModelTest::test_foo"
find_bad_commit(target_test=target_test)
