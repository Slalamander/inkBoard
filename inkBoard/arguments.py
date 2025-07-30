"""
Handles command line arguments for inkboard
"""
import argparse
from . import constants as const

DESIGNER_MOD = const.DESIGNER_INSTALLED

if const.DESIGNER_INSTALLED:
    ##For this: ensure the designer can be imported without the window being build etc.
    ##i.e. move a lot of the init into a runner file
    import inkBoarddesigner
    designer_version = inkBoarddesigner.__version__

def pop_base_args(args) -> dict:
    "Returns a dict with the base argparse arguments removed (i.e. anything that is not command)"
    d = vars(args).copy()
    d.pop("logs")
    d.pop("quiet")
    d.pop("verbose")
    d.pop("command")
    return d


def command_version(*args):
    print(f"inkBoard Version: {const.__version__}")
    if DESIGNER_MOD:
        print(f"inkBoard designer Version: {designer_version}")
    return 0

def command_logs(args):
    from ._logger import run_logger
    return run_logger(**pop_base_args(args))

def command_designer(args):
    if not DESIGNER_MOD:
        print("Running inkBoard designer requires the inkBoard designer to be installed")
        print("Run 'pip install inkBoarddesigner' to install it")
        return 1

    inkBoarddesigner.run_designer(args)

def command_install(args):
    from .packaging import run_install_command
    return run_install_command(**pop_base_args(args))

def command_pack(args):
    from .packaging import create_config_package
    return create_config_package(**pop_base_args(args))


PRE_CORE_ACTIONS = {
    const.COMMAND_VERSION: command_version,
    const.COMMAND_DESIGNER: command_designer,
    const.COMMAND_INSTALL: command_install,
    const.COMMAND_LOGS: command_logs,
}
"Action that can/have to be run before creating the CORE object"

POST_CORE_ACTIONS = {
    const.COMMAND_PACK: command_pack
}
"Actions to run after creating the CORE object, but before doing any setup otherwise."



def parse_args():

    ##Code layout mainly used from esphome command line interface

    base_parser = argparse.ArgumentParser(add_help=False)
    base_parser.add_argument('--logs',default=None,
                        choices=const.LOG_LEVELS, help='set log level manually, takes precedent over the --quiet and --verbose flags. If None are set, it defaults to WARNING')    
    base_parser.add_argument('-q', '--quiet', action='store_true', dest='quiet',
                        help="Disables all inkBoard logs")
    base_parser.add_argument('-v', '--verbose', action='store_true', dest='verbose',
                        help="Enables all inkBoard logs")

    parser = argparse.ArgumentParser(parents=[base_parser],
                            description="""
                                Aims to make it easy to design dashboards for a variety of devices.
                            """)

    subparsers = parser.add_subparsers(
        help="The mode or command to run inkBoard with:", dest="command", metavar="command"
    )
    subparsers.required = True

    subparsers.add_parser(const.COMMAND_VERSION, 
                        help="Print the inkBoard version and optionally designer version, then exits.")

    parser_run = subparsers.add_parser(
        const.COMMAND_RUN, help="Runs inkBoard using the provided config file"
    )

    parser_run.add_argument(const.ARGUMENT_CONFIG, help="The YAML file used for the dashboard", default=const.DEFAULT_CONFIG)
    ##Could optionally add the RAISE flag to this.

    if DESIGNER_MOD:
        inkBoarddesigner._add_parser(subparsers, const.COMMAND_DESIGNER)
    else:
        designer_parser = subparsers.add_parser(const.COMMAND_DESIGNER, 
                                            description="inkBoard designer is not installed",
                                            help="Runs inkBoard in designer mode. inkBoarddesigner must be installed for it.")

    parser_pack = subparsers.add_parser(
        const.COMMAND_PACK, help="Creates an inkBoard package using the provided config file"
    )

    parser_pack.add_argument(const.ARGUMENT_CONFIG, help="The YAML file used for the package")
    parser_pack.add_argument("name", help="""
                            The name of the package file. Must have no suffix, or end in .zip
                            """, default=None, nargs='?')
    
    parser_pack.add_argument("--all", action='store_true', dest='pack_all', help="Creates a complete package of the config")
    parser_pack.add_argument("--config", action='store_true', help="Includes the configuration file and requires files and folders in the package")
    parser_pack.add_argument("--platform", action='store_true', help="Includes the platform module in the package")
    parser_pack.add_argument("--integrations", action='store_true', help="Includes the loaded integrations in the package")

    parser_install = subparsers.add_parser(
        const.COMMAND_INSTALL, help="Installs inkBoard packages or requirements from a config folder"
    )

    parser_install.add_argument("--upgrade", "-U", action='store_true', help="""
                            Checks if any integrations and platforms passed can be upgraded from the inkBoard package index.
                            """, dest="upgrade")
    parser_install.add_argument("--dev", "-D", action='store_true', help="""
                            Enables downloading packages from the developer branch.
                            """, dest="upgrade")
    parser_install.add_argument("--local", "-L", help="""
                            Installs local files. Pass appropriate file arguments.
                            Accepts:\n
                                -  (paths to) ZIP files of integrations, platforms, or packages
                                -  (paths to) a configuration YAML file. This creates a list of install requirements for custom integrations and all requirements.txt files found in the configuration directory and sub directories.\n
                                -  The names of a platform or integration already internally installed, to install its requirements. This case is usually already handled by the other methods.
                            """, dest="local_installs", default=[], nargs='?')
    parser_install.add_argument("--platforms",  "-P", help="""
                            Downloads and installs provided platforms. If --upgrade is not provided, nothing is done if the platform is already installed.
                            """, dest="platforms", default=[], nargs='?')
    parser_install.add_argument("--integrations",  "-I", help="""
                            Downloads and installs provided integrations. If --upgrade is not provided, nothing is done if the integration is already installed.
                            """, dest="integrations", default=[], nargs='?')
    parser_install.add_argument("index", "--index", "-X", help="""
                            Manually determines the install type for each argument. Names ending with .zip, .txt, .yaml and .yml are handled as arguments to --local.
                            Other arguments are looked up in the inkBoard index and downloaded and installed if needed.
                            """, dest="index_installs", default=[], nargs='?')
    # raise Exception("Go implement the functions for the install arguments. But first get the index repo set up probably.")
    ##installer command
    #[x]: rename file to type/installtype; options will be integration, platform and file
    #[x]: names argument; the name(s) of things to install.
    #[x]: shorthands (-f, -i, -p); either in the function or somehow in the parser make them exclusive -> no, add them as regular options, with nargs
    #[ ]: FOR LATER: add argument that allows installation from github links
    ## ok so: seperate arg for each type, make the command call everything at once

    parser_install.add_argument('--no-input', help="Disables any input prompts that are deemed optional", action='store_true')

    parser_logs = subparsers.add_parser(
        const.COMMAND_LOGS, help="Provided connections to instance logs"
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"Version: {const.__version__}",
        help="Prints the inkBoard version and exits.",
    )

    return parser.parse_args()


# args = parse_args()
