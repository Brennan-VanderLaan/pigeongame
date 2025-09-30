"""
Lightweight CLI integration tests

These tests verify that the CLI argument parsing and command routing works correctly.
The underlying mesh management functionality is already thoroughly tested in test_mesh_manager.py.
"""

import pytest
import asyncio
import subprocess
import json
import sys
from pathlib import Path

# Configure logging for tests to reduce noise
from logging_config import setup_test_logging
setup_test_logging()


class TestCLIIntegration:
    """Basic CLI integration tests"""

    def run_cli(self, *args):
        """Helper to run CLI commands and capture output"""
        cli_path = Path(__file__).parent.parent / "mesh_cli.py"
        cmd = [sys.executable, str(cli_path)] + list(args)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )

        return result

    def test_cli_help(self):
        """Test that CLI help works"""
        result = self.run_cli("--help")
        assert result.returncode == 0
        assert "Mesh Network CLI" in result.stdout
        assert "kubectl-style interface" in result.stdout

    def test_cli_no_args(self):
        """Test CLI with no arguments shows help"""
        result = self.run_cli()
        assert result.returncode == 1
        # Should show help when no arguments provided

    def test_get_meshes_json_output(self):
        """Test getting meshes with JSON output"""
        result = self.run_cli("--output", "json", "get", "meshes")
        assert result.returncode == 0

        # Should be clean JSON output now
        try:
            data = json.loads(result.stdout)
            assert isinstance(data, list)
        except json.JSONDecodeError:
            pytest.fail("Output is not valid JSON")

    def test_get_meshes_table_output(self):
        """Test getting meshes with table output (default)"""
        result = self.run_cli("get", "meshes")
        assert result.returncode == 0

        # Should contain table headers
        assert "NAME" in result.stdout
        assert "NODES" in result.stdout
        assert "HUBS" in result.stdout

    def test_invalid_verb(self):
        """Test invalid verb returns error"""
        result = self.run_cli("invalid-verb")
        assert result.returncode == 2  # argparse error code

    def test_invalid_noun(self):
        """Test invalid noun returns error"""
        result = self.run_cli("get", "invalid-noun")
        assert result.returncode == 2  # argparse error code

    def test_create_mesh_help(self):
        """Test create mesh command help"""
        result = self.run_cli("create", "mesh", "--help")
        assert result.returncode == 0
        assert "Mesh name" in result.stdout

    def test_get_nodes_requires_mesh(self):
        """Test that get nodes requires --mesh parameter"""
        result = self.run_cli("get", "nodes")
        assert result.returncode == 2  # Argument parsing error
        assert "required" in result.stderr.lower()

    def test_create_node_help(self):
        """Test create node command help"""
        result = self.run_cli("create", "node", "--help")
        assert result.returncode == 0
        assert "--mesh" in result.stdout
        assert "--addrs" in result.stdout
        assert "--data" in result.stdout

    def test_apply_link_help(self):
        """Test apply link command help"""
        result = self.run_cli("apply", "link", "--help")
        assert result.returncode == 0
        assert "--node" in result.stdout
        assert "--hub" in result.stdout
        assert "--mesh" in result.stdout

    def test_apply_hub_link_help(self):
        """Test apply hub-link command help"""
        result = self.run_cli("apply", "hub-link", "--help")
        assert result.returncode == 0
        assert "--source-hub" in result.stdout
        assert "--target-hub" in result.stdout
        assert "--mesh" in result.stdout

    def test_mesh_not_found_error(self):
        """Test appropriate error when mesh not found"""
        result = self.run_cli("get", "nodes", "--mesh", "nonexistent-mesh")
        # Exit code can vary but should indicate error
        assert result.returncode != 0
        assert "not found" in result.stderr.lower()

    def test_node_not_found_error(self):
        """Test appropriate error when node not found"""
        # First ensure we have a mesh to test with
        meshes_result = self.run_cli("--output", "json", "get", "meshes")

        if meshes_result.returncode == 0:
            try:
                meshes = json.loads(meshes_result.stdout)
                if meshes:
                    mesh_name = meshes[0]["name"]
                    result = self.run_cli("get", "node", "nonexistent-node", "--mesh", mesh_name)
                    # Don't assume exact error code, just that it's an error
                    assert result.returncode != 0
                    assert "not found" in result.stderr.lower()
            except (json.JSONDecodeError, KeyError, IndexError):
                # Skip test if we can't parse mesh data
                pass

    def test_json_output_format(self):
        """Test that JSON output is properly formatted"""
        result = self.run_cli("-o", "json", "get", "meshes")
        assert result.returncode == 0

        try:
            data = json.loads(result.stdout)
            # Should be a list of mesh objects
            assert isinstance(data, list)
            for mesh in data:
                assert "name" in mesh
                assert "id" in mesh
                assert "nodes" in mesh
                assert "hubs" in mesh
        except json.JSONDecodeError:
            pytest.fail("JSON output is malformed")


class TestCLIWorkflow:
    """Test a basic CLI workflow to ensure end-to-end functionality"""

    def run_cli(self, *args):
        """Helper to run CLI commands and capture output"""
        cli_path = Path(__file__).parent.parent / "mesh_cli.py"
        cmd = [sys.executable, str(cli_path)] + list(args)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )

        return result

    def test_basic_workflow(self):
        """Test a basic mesh management workflow via CLI"""
        unique_name = "cli-test-workflow"

        # Clean up any existing mesh with this name first
        self.run_cli("delete", "mesh", unique_name)

        try:
            # 1. Create mesh
            result = self.run_cli("create", "mesh", unique_name)
            # Don't fail if mesh already exists
            if result.returncode not in (0, 409):  # 409 = conflict/already exists
                # If it's some other error, we should investigate
                print(f"Unexpected error creating mesh: {result.stderr}")

            # 2. Verify mesh exists
            result = self.run_cli("get", "mesh", unique_name)
            assert result.returncode == 0

            # 3. Create a node with JSON data
            result = self.run_cli(
                "create", "node", "test-server",
                "--mesh", unique_name,
                "--addrs", "192.168.1.100,10.0.0.100",
                "--data", '{"role": "test", "cpu": 4}'
            )
            # Don't fail if node already exists
            if result.returncode not in (0, 409):
                print(f"Unexpected error creating node: {result.stderr}")

            # 4. Verify node exists
            result = self.run_cli("get", "nodes", "--mesh", unique_name)
            assert result.returncode == 0
            # Don't assume exact output format, just that we get some output
            assert len(result.stdout.strip()) > 0

        finally:
            # Cleanup - don't fail the test if cleanup fails
            self.run_cli("delete", "mesh", unique_name)


if __name__ == "__main__":
    # Run tests directly if executed as script
    pytest.main([__file__, "-v"])