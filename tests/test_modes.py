from unittest.mock import patch

import pytest

from pytest_picked.modes import Branch, OnlyChanged, Unstaged


@pytest.fixture
def git_repository(testdir):
    gitroot = testdir.mkdir("gitroot")
    gitroot.chdir()

    try:
        assert testdir.run("git", "init").ret == 0
    except FileNotFoundError:
        pytest.skip("required executable 'git' not found")
    else:
        git_user = ["git", "config", "user.name", "Pytest Picked"]
        git_email = ["git", "config", "user.email", "picked@pytest.com"]
        assert testdir.run(*git_user).ret == 0
        assert testdir.run(*git_email).ret == 0

    assert testdir.run("git", "commit", "--allow-empty", "-m_").ret == 0
    yield gitroot


class TestUnstaged:
    def test_should_return_git_status_command(self):
        mode = Unstaged([])
        command = mode.command()

        assert isinstance(command, list)
        assert mode.command() == ["git", "status", "--short"]

    @pytest.mark.parametrize(
        "line,expected_line",
        [
            ("D  tests/migrations/auto.py", None),
            ("R  tests/from-school.csv -> test_new_things.py", "test_new_things.py"),
            (
                "R  tests/from-school.csv -> tests/test_new_things.py",
                "tests/test_new_things.py",
            ),
            (" M test.py", "test.py"),
            ("AD test.py", None),
            ("?? api/", "api/"),
        ],
    )
    def test_parser_should_ignore_no_paths_characteres(self, line, expected_line):
        mode = Unstaged([])
        parsed_line = mode.parser(line)

        assert parsed_line == expected_line

    def test_should_list_unstaged_changed_files_as_affected_tests(self):
        test_conventions = dict()
        test_conventions["file"] = ["test_*.py", "*_test.py"]
        raw_output = (
            b"R  school/migrations/from-school.csv -> test_new_things.py\n"
            + b"D  school/migrations/0032_auto_20180515_1308.py\n"
            + b"?? Pipfile\n"
            + b"!! school/tests/test_rescue_students.py\n"
            + b"C  tests/\n"
            + b" M .pre-commit-config.yaml\n"
            + b" M picked.py\n"
            + b"A  setup.py\n"
            + b" U tests/test_pytest_picked.py\n"
            + b"?? random/tests/\n"
            + b" M intestine.py\n"
            + b"?? api/\n"
            + b" M tests_new/intestine.py\n"
        )

        with patch("pytest_picked.modes.subprocess.run") as subprocess_mock:
            subprocess_mock.return_value.stdout = raw_output
            mode = Unstaged(test_conventions)
            files, folders = mode.affected_tests()

        expected_files = [
            "test_new_things.py",
            "school/tests/test_rescue_students.py",
            "tests/test_pytest_picked.py",
        ]
        expected_folders = ["tests/", "random/tests/", "api/"]

        assert files == expected_files
        assert folders == expected_folders


class TestBranch:
    def test_should_return_command_that_list_all_changed_files(self):
        mode = Branch([])
        command = mode.command()

        assert isinstance(command, list)
        assert mode.command() == [
            "git",
            "diff",
            "--name-status",
            "--relative",
            "master",
        ]

    def test_should_return_command_that_list_all_changed_files_for_different_branch(
        self,
    ):
        mode = Branch([], "main")
        command = mode.command()

        assert isinstance(command, list)
        assert mode.command() == ["git", "diff", "--name-status", "--relative", "main"]

    @pytest.mark.parametrize(
        "line,expected_line",
        [
            ("D       tests/migrations/auto.py", None),
            (
                "R098    tests/test_pytest_picked.py     "
                "tests/test_pytest_picked.py",
                "tests/test_pytest_picked.py",
            ),
            ("M       test.py", "test.py"),
            ("AD      test.py", None),
        ],
    )
    def test_parser_should_ignore_no_paths_characters(self, line, expected_line):
        mode = Branch([])
        parsed_line = mode.parser(line)

        assert parsed_line == expected_line

    def test_should_list_branch_changed_files_as_affected_tests(self):
        raw_output = (
            b"D       pytest_picked.py\n"
            b"R066    tests/test_pytest_picked.py     "
            b"tests/test_new_pytest_picked.py\n"
            b"M       tests/test_other_module.py"
        )
        test_conventions = dict()
        test_conventions["file"] = ["test_*.py", "*_test.py"]

        with patch("pytest_picked.modes.subprocess.run") as subprocess_mock:
            subprocess_mock.return_value.stdout = raw_output
            mode = Branch(test_conventions)
            files, folders = mode.affected_tests()

        expected_files = [
            "tests/test_new_pytest_picked.py",
            "tests/test_other_module.py",
        ]
        expected_folders = []

        assert files == expected_files
        assert folders == expected_folders

    def test_should_list_changed_files(self, testdir, git_repository):
        git_repository.join("test_gitroot").new(ext="py").write(b"", "wb")
        assert testdir.run("git", "add", ".").ret == 0

        output = set(Branch([]).git_output().splitlines())
        assert output == {"A       test_gitroot.py"}

    def test_should_only_list_pytest_root_changed_files(self, git_repository, testdir):
        git_repository.join("test_gitroot").new(ext="py").write(b"", "wb")
        pytestroot = git_repository.mkdir("pytestroot")
        pytestroot.join("test_pytestroot").new(ext="py").write(b"", "wb")
        assert testdir.run("git", "add", ".").ret == 0

        output = set(Branch([]).git_output().splitlines())
        assert output == {
            "A       test_gitroot.py",
            "A       pytestroot/test_pytestroot.py",
        }

        pytestroot.chdir()
        output = set(Branch([]).git_output().splitlines())
        assert output == {"A       test_pytestroot.py"}


class TestOnlyChanged:
    def test_should_return_git_diff_command(self):
        mode = OnlyChanged([])
        command = mode.command()

        assert isinstance(command, list)
        assert mode.command() == ["git", "diff"]

    @pytest.mark.parametrize(
        "line,expected_line",
        [
            (
                "@@ -191,29 +191,8 @@ class TestPytestPicked:",
                "@@ -191,29 +191,8 @@ class TestPytestPicked:",
            ),
            ("-    def test_positive_update_limit(self):", None),
            ("--- a/tests/foreman/cli/test_host_collection.py", None),
            (
                "+++ b/tests/pytestpicked/test_positive",
                "tests/pytestpicked/test_positive",
            ),
            ("+    @pytest.mark.tier2", "+    @pytest.mark.tier2"),
            ("+    def test", "+    def test"),
            ("-def test_positive", None),
        ],
    )
    def test_parser_should_ignore_no_paths_characters(self, line, expected_line):
        mode = OnlyChanged([])
        parsed_line = mode.parser(line)

        assert parsed_line == expected_line

    def test_should_list_changed_tests(self):
        raw_output = (
            b"\n+++ b/tests/pytestpicked/test_modes1.py"
            b"\n@@ -191,29 +191,8 @@ class TestPytestPicked(CLITestCase):"
            b"\n+    def test_with_class(self):"
            b"\n+++ b/tests/pytestpicked/test_modes1.py"
            b"\n@@ -191,29 +191,8 @@ class TestPytestPicked(CLITestCase):"
            b"\n+++ b/tests/pytestpicked/test_modes1.py"
            b"\n+    def test_with_duplicate_classes(self):"
            b"\n+++ b/tests/pytestpicked/test_modes2.py"
            b"\n@@ -191,29 +191,8 @@ class TestPytestPicked:"
            b"\n+    def test_with_class_1(self):"
            b"\n+    def test_with_class_2(self):"
            b"\n+++ b/tests/pytestpicked/test_modes3.py"
            b"\n+    def test_without_class(self):"
            b"\n+++ b/tests/pytestpicked/test_modes4.py"
            b"\n+    def invalid_function(self):"
            b"\n+++ b/tests/pytestpicked/test_modes5.py"
            b"\n+    def invalid_test(self):"
            b"\n+++ b/tests/pytestpicked/test_modes6.py"
            b"\n@@ -191,29 +191,8 @@ class InvalidClass:"
        )
        test_conventions = dict()
        test_conventions["file"] = ["test_*.py", "*_test.py"]
        test_conventions["class"] = ["Test", "Check"]
        test_conventions["function"] = ["test", "check_*"]

        with patch("pytest_picked.modes.subprocess.run") as subprocess_mock:
            subprocess_mock.return_value.stdout = raw_output
            mode = OnlyChanged(test_conventions, True)
            tests, folders = mode.affected_tests()
        expected_tests = [
            "tests/pytestpicked/test_modes1.py::TestPytestPicked",
            "tests/pytestpicked/test_modes2.py::TestPytestPicked",
            "tests/pytestpicked/test_modes3.py::test_without_class",
        ]

        assert tests == expected_tests
