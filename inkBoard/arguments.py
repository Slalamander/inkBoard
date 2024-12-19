"""
Handles command line arguments for inkboard
"""
import argparse
from . import constants as const
from .logging import LOG_LEVELS

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

def command_designer(args):
    if not DESIGNER_MOD:
        print("Running inkBoard designer require the inkBoard designer to be installed")
        print("Run 'pip install inkBoarddesigner' to install it")
        return 1

    inkBoarddesigner.run_designer(args)

def command_install(args):
    from .packaging import command_install
    return command_install(**pop_base_args(args))

def command_pack(args):
    from .packaging import create_config_package
    return create_config_package(**pop_base_args(args))


PRE_CORE_ACTIONS = {
    const.COMMAND_VERSION: command_version,
    const.COMMAND_DESIGNER: command_designer,
    const.COMMAND_INSTALL: command_install
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
                        choices=LOG_LEVELS, help='set log level manually, takes precedent over the --quiet and --verbose flags. If None are set, it defaults to WARNING')    
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

    parser_install.add_argument("file", help="""
                            The file to install. If it is a ZIP file, inkBoard will check if it is an inkBoard compatible one (Either an inkBoard package, or a zip of a platform or integration folder).
                            If a YAML file, inkBoard will go through the base directory, the files folder and the custom folder and call pip install on any files it finds titled requirements.txt. In the custom integration folder, it will also take care of installing requirements for the integrations presents.
                            If it is platform or integration, appended by a name, inkBoard will go through the install process of that respective platform/integration, provided it is installed internally.
                            If not supplied, the installer will look for all suitable ZIP files in the current directory.
                            """, default=None, nargs='?')
    ##How to deal with passing the name part of the command?
    
    parser_install.add_argument("name", help="The name of platform or integration to install. This is not used if the file command is not one of integration or platform.",
                                default=None, nargs="?")

    parser_install.add_argument('--no-input', help="Disables any input prompts that are deemed optional", action='store_true')

    parser.add_argument(
        "--version",
        action="version",
        version=f"Version: {const.__version__}",
        help="Prints the inkBoard version and exit.",
    )

    return parser.parse_args()


args = parse_args()
