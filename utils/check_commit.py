import argparse
import json
import os
import re
import subprocess
import requests


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

if len(result.stderr) > 0:
    if "ERROR: not found: " in result.stderr:
        print("test not found in this commit")
        exit(0)
    else:
        print(f"pytest failed to run: {{result.stderr}}")
        exit(-1)
elif f"{target_test} FAILED" in result.stdout:
    print("test failed")
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

    if "error: bisect run failed" in result.stderr:
        index = result.stderr.find("error: bisect run failed")
        bash_error = result.stderr[index:]

        error_msg = f"Error when running git bisect:\nbash error: {bash_error}"

        pattern = "pytest failed to run: .+"
        pytest_errors = re.findall(pattern, result.stdout)
        if len(pytest_errors) > 0:
            pytest_error = pytest_errors[0]
            index = pytest_error.find("pytest failed to run: ")
            index += len("pytest failed to run: ")
            pytest_error = pytest_error[index:]
            error_msg += f"pytest error: {pytest_error}"

        raise ValueError(error_msg)

    pattern = r"(.+) is the first bad commit"
    commits = re.findall(pattern, result.stdout)

    bad_commit = None
    if len(commits) > 0:
        bad_commit = commits[0]

    print(f"Between `start_commit` {start_commit} and `end_commit` {end_commit}")
    print(f"bad_commit: {bad_commit}\n")

    return bad_commit


def get_commit_info(commit):
    pr_number = None
    author = None
    merged_author = None

    url = f"https://api.github.com/repos/huggingface/transformers/commits/{commit}/pulls"
    pr_info_for_commit = requests.get(url).json()

    if len(pr_info_for_commit) > 0:
        pr_number = pr_info_for_commit[0]["number"]

        url = f"https://api.github.com/repos/huggingface/transformers/pulls/{pr_number}"
        pr_for_commit = requests.get(url).json()
        pr_title = pr_for_commit["title"]
        author = pr_for_commit["user"]["login"]


        merged_author = pr_for_commit["merged_by"]["login"]

    if author is None:
        url = f"https://api.github.com/repos/huggingface/transformers/commits/{commit}"
        commit_info = requests.get(url).json()
        author = commit_info["author"]["login"]

    return {"commit": commit, "pr_number": pr_number, "author": author, "merged_by": merged_author}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start_commit", type=str, required=True, help="The starting commit hash.")
    parser.add_argument("--end_commit", type=str, required=True, help="The ending commit hash.")
    parser.add_argument("--test", type=str, help="The test to check.")
    parser.add_argument("--file", type=str, help="The report file.")
    parser.add_argument("--output_file", type=str, required=True, help="The path of the output file.")
    args = parser.parse_args()

    print(f"start_commit: {args.start_commit}")
    print(f"end_commit: {args.end_commit}")

    assert len({args.file is None, args.file is None}) == 1

    if args.test is not None:
        commit = find_bad_commit(target_test=args.test, start_commit=args.start_commit, end_commit=args.end_commit)
        with open(args.output_file, "w", encoding="UTF-8") as fp:
            fp.write(f"{args.test}\n{commit}")
    elif os.path.isfile(args.file):
        with open(args.file, "r", encoding="UTF-8") as fp:
            reports = json.load(fp)

        for model in reports:
            failed_tests = reports[model]["single-gpu"]
            failed_tests_with_bad_commits = []
            for test in failed_tests:
                commit = find_bad_commit(target_test=test, start_commit=args.start_commit, end_commit=args.end_commit)
                info = {"test": test, "commit": commit}
                info.update(get_commit_info(commit))
                failed_tests_with_bad_commits.append(info)
            reports[model]["single-gpu"] = failed_tests_with_bad_commits

        with open(args.output_file, "w", encoding="UTF-8") as fp:
            json.dump(reports, fp, ensure_ascii=False, indent=4)

    # python3 check_commit2.py --start_commit 54705c8a --end_commit 317e069e --file ci_results_run_models_gpu/new_model_failures.json --output_file new_model_failures_with_bad_commit.json
    # python3 check_commit2.py --start_commit 54705c8a --end_commit 317e069e --test tests/models/vit/test_modeling_vit.py::ViTModelTest::test_foo --output_file new_model_failures_with_bad_commit.txt
