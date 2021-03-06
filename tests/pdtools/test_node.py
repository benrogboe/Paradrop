import click
from click.testing import CliRunner
from mock import patch, MagicMock

from pdtools import node


@patch("pdtools.util.open_yaml_editor")
@patch("pdtools.node.util.format_result")
@patch("pdtools.node.ParadropClient")
def test_simple_node_commands(ParadropClient, format_result, open_yaml_editor):
    commands = [
        ["create-user", "test@example.com"],
        ["describe-audio"],
        ["describe-chute", "test"],
        ["describe-chute-cache", "test"],
        ["describe-chute-configuration", "test"],
        ["describe-chute-network-client", "test", "wifi", "00:11:22:33:44:55"],
        ["describe-pdconf"],
        ["describe-provision"],
        ["export-configuration"],
        ["generate-configuration"],
        ["help"],
        ["import-ssh-key", "/dev/null"],
        ["list-audio-modules"],
        ["list-audio-sinks"],
        ["list-audio-sources"],
        ["list-chute-network-clients", "test", "wifi"],
        ["list-chute-networks", "test"],
        ["list-chutes"],
        ["list-snap-interfaces"],
        ["list-ssh-keys"],
        ["load-audio-module", "module-test"],
        ["login"],
        ["logout"],
        ["remove-chute-network-client", "test", "wifi", "00:11:22:33:44:55"],
        ["set-sink-volume", "default", "0"],
        ["set-source-volume", "default", "0"],
        ["trigger-pdconf"]
    ]

    client = MagicMock()
    client.generate_config.return_value = {}
    client.get_config.return_value = {}
    ParadropClient.return_value = client

    format_result.return_value = "result"
    open_yaml_editor.return_value = "", True

    runner = CliRunner()
    for command in commands:
        result = runner.invoke(node.root, command, obj={})
        print("Command {} exit code {}".format(command[0], result.exit_code))
        if result.exception is not None:
            print(result.exception)
        assert result.exit_code == 0
