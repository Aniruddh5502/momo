import unittest
import time
from pathlib import Path
from typing import List, Tuple
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.live import Live

# We import the tests as modules to discover them
import momobot.tests.test_prompt_builder
import momobot.tests.test_config_loading

# Add other existing tests from the folder if they exist
try:
    import momobot.tests.test_agent
    import momobot.tests.test_tool_ui
    import momobot.tests.test_ui_sync
    import momobot.tests.test_write
except ImportError:
    pass

class TestManager:
    """
    Orchestrates the execution of all tests in the momobot.tests package
    and renders the results using Rich.
    """
    def __init__(self):
        self.console = Console()
        self.loader = unittest.TestLoader()
        self.suite = unittest.TestSuite()
        self._discover_tests()

    def _discover_tests(self):
        """Collects all test cases from the registered test modules."""
        test_modules = [
            momobot.tests.test_prompt_builder,
            momobot.tests.test_config_loading,
        ]
        
        # Try to include the legacy tests found in the directory
        legacy_tests = [
            "momobot.tests.test_agent",
            "momobot.tests.test_tool_ui",
            "momobot.tests.test_ui_sync",
            "momobot.tests.test_write"
        ]
        
        for mod_name in legacy_tests:
            try:
                # Dynamic import for legacy tests to avoid crash if missing
                import importlib
                mod = importlib.import_module(mod_name)
                test_modules.append(mod)
            except ImportError:
                continue

        for module in test_modules:
            self.suite.addTests(self.loader.loadTestsFromModule(module))

    def run_all(self):
        """Executes the suite and prints a formatted report."""
        self.console.print(Panel(
            "[bold magenta]Momobot Test Suite Manager[/bold magenta]\n"
            "[dim]Executing all system and unit tests...[/dim]",
            border_style="magenta",
            expand=False
        ))

        results = []
        total_start_time = time.time()

        # We use a custom result object to capture details without printing to stdout
        class RichTestResult(unittest.TextTestResult):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.detailed_results = []

            def addSuccess(self, test):
                super().addSuccess(test)
                self.detailed_results.append((test.id(), "PASSED", "green", None))

            def addError(self, test, err):
                super().addError(test, err)
                self.detailed_results.append((test.id(), "ERROR", "red", err))

            def addFailure(self, test, err):
                super().addFailure(test, err)
                self.detailed_results.append((test.id(), "FAILED", "red", err))


        # Run the tests
        runner = unittest.TextTestRunner(resultclass=RichTestResult, verbosity=0)
        result = runner.run(self.suite)
        
        total_end_time = time.time()
        duration = total_end_time - total_start_time

        # Render the Table
        table = Table(
            title="Test Execution Report",
            show_header=True,
            header_style="bold white",
            border_style="dim"
        )
        table.add_column("Test ID", style="cyan")
        table.add_column("Status", justify="center")
        table.add_column("Details", style="dim")

        for test_id, status, color, err in result.detailed_results:
            err_msg = str(err[1]) if err else ""
            table.add_row(test_id, f"[{color}]{status}[/{color}]", err_msg)

        self.console.print(table)

        # Summary Panel
        summary_text = (
            f"Total Tests: {result.testsRun} | "
            f"Passed: {result.testsRun - len(result.failures) - len(result.errors)} | "
            f"Failed: {len(result.failures)} | "
            f"Errors: {len(result.errors)} | "
            f"Time: {duration:.2f}s"
        )
        
        color = "green" if result.wasSuccessful() else "red"
        self.console.print(Panel(
            f"[{color}]{summary_text}[/{color}]",
            title="Summary",
            border_style=color,
            expand=False
        ))

        return result.wasSuccessful()

if __name__ == "__main__":
    manager = TestManager()
    success = manager.run_all()
    exit(0 if success else 1)
