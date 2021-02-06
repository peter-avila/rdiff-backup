import argparse
import sys
import yaml
from rdiffbackup.utils.argopts import BooleanOptionalAction, SelectAction

# The default regexp for not compressing those files
# compat200: it is also used by Main.py to avoid having a 2nd default
DEFAULT_NOT_COMPRESSED_REGEXP = (
    "(?i).*\\.("
    "gz|z|bz|bz2|tgz|zip|zst|rpm|deb|"
    "jpg|jpeg|gif|png|jp2|mp3|mp4|ogg|ogv|oga|ogm|avi|wmv|"
    "mpeg|mpg|rm|mov|mkv|flac|shn|pgp|"
    "gpg|rz|lz4|lzh|lzo|zoo|lharc|rar|arj|asc|vob|mdf|tzst|webm"
    ")$"
)

# === DEFINE COMMON PARSER ===


COMMON_PARSER = argparse.ArgumentParser(
    add_help=False,
    description="[parent] common options to all actions")
COMMON_PARSER.add_argument(
    "--api-version", type=int,
    help="[opt] integer to set the API version forcefully used")
COMMON_PARSER.add_argument(
    "--current-time", type=int,
    help="[opt] fake the current time in seconds (for testing)")
COMMON_PARSER.add_argument(
    "--force", action="store_true",
    help="[opt] force action (caution, the result might be dangerous)")
COMMON_PARSER.add_argument(
    "--fsync", default=True, action=BooleanOptionalAction,
    help="[opt] do (or not) often sync the file system (_not_ doing it is faster but can be dangerous)")
COMMON_PARSER.add_argument(
    "--null-separator", action="store_true",
    help="[opt] use null instead of newline in input and output files")
COMMON_PARSER.add_argument(
    "--new", default=False, action=BooleanOptionalAction,
    help="[opt] enforce (or not) the usage of the new parameters")
COMMON_PARSER.add_argument(
    "--chars-to-quote", "--override-chars-to-quote",
    type=str, metavar="CHARS",
    help="[opt] string of characters to quote for safe storing")
COMMON_PARSER.add_argument(
    "--parsable-output", action="store_true",
    help="[opt] output in computer parsable format")
COMMON_PARSER.add_argument(
    "--remote-schema", type=str,
    help="[opt] alternative command to call remotely rdiff-backup")
COMMON_PARSER.add_argument(
    "--remote-tempdir", type=str, metavar="DIR_PATH",
    help="[opt] use path as temporary directory on the remote side")
COMMON_PARSER.add_argument(
    "--restrict-path", type=str, metavar="DIR_PATH",
    help="[opt] restrict remote access to given path")
COMMON_PARSER.add_argument(
    "--restrict-mode", type=str,
    choices=["read-write", "read-only", "update-only"], default="read-write",
    help="[opt] restriction mode for directory (default is 'read-write')")
COMMON_PARSER.add_argument(
    "--ssh-compression", default=True, action=BooleanOptionalAction,
    help="[opt] use SSH without compression with default remote-schema")
COMMON_PARSER.add_argument(
    "--tempdir", type=str, metavar="DIR_PATH",
    help="[opt] use given path as temporary directory")
COMMON_PARSER.add_argument(
    "--terminal-verbosity", type=int, choices=range(0, 10),
    help="[opt] verbosity on the terminal, default given by --verbosity")
COMMON_PARSER.add_argument(
    "--use-compatible-timestamps", action="store_true",
    help="[opt] use hyphen '-' instead of colon ':' to represent time")
COMMON_PARSER.add_argument(
    "-v", "--verbosity", type=int, choices=range(0, 10), default=3,
    help="[opt] overall verbosity on terminal and in logfiles (default is 3)")


# === DEFINE PARENT PARSERS ===


COMMON_COMPAT200_PARSER = argparse.ArgumentParser(
    add_help=False,
    description="[parent] common options to all actions (compat200)")
restrict_group = COMMON_COMPAT200_PARSER.add_mutually_exclusive_group()
restrict_group.add_argument(
    "--restrict", type=str, metavar="DIR_PATH",
    help="[deprecated] restrict remote access to given path, in read-write mode")
restrict_group.add_argument(
    "--restrict-read-only", type=str, metavar="DIR_PATH",
    help="[deprecated] restrict remote access to given path, in read-only mode")
restrict_group.add_argument(
    "--restrict-update-only", type=str, metavar="DIR_PATH",
    help="[deprecated] restrict remote access to given path, in backup update mode")
COMMON_COMPAT200_PARSER.add_argument(
    "--ssh-no-compression", action="store_true",
    help="[deprecated] use SSH without compression with default remote-schema")

SELECTION_PARSER = argparse.ArgumentParser(
    add_help=False,
    description="[parent] options related to file selection")
SELECTION_PARSER.add_argument(
    "--SELECT", action=SelectAction, metavar="GLOB",
    help="[sub] SELECT files according to glob pattern")
SELECTION_PARSER.add_argument(
    "--SELECT-device-files", action=SelectAction, type=bool, default=True,
    help="[sub] SELECT device files")
SELECTION_PARSER.add_argument(
    "--SELECT-fifos", action=SelectAction, type=bool, default=True,
    help="[sub] SELECT fifo files")
SELECTION_PARSER.add_argument(
    "--SELECT-filelist", action=SelectAction, metavar="LIST_FILE",
    help="[sub] SELECT files according to list in given file")
SELECTION_PARSER.add_argument(
    "--SELECT-filelist-stdin", action=SelectAction, type=bool,
    help="[sub] SELECT files according to list from standard input")
SELECTION_PARSER.add_argument(
    "--SELECT-symbolic-links", action=SelectAction, type=bool, default=True,
    help="[sub] SELECT symbolic links")
SELECTION_PARSER.add_argument(
    "--SELECT-sockets", action=SelectAction, type=bool, default=True,
    help="[sub] SELECT socket files")
SELECTION_PARSER.add_argument(
    "--SELECT-globbing-filelist", action=SelectAction, metavar="GLOBS_FILE",
    help="[sub] SELECT files according to glob list in given file")
SELECTION_PARSER.add_argument(
    "--SELECT-globbing-filelist-stdin", action=SelectAction, type=bool,
    help="[sub] SELECT files according to glob list from standard input")
SELECTION_PARSER.add_argument(
    "--SELECT-other-filesystems", action=SelectAction, type=bool, default=True,
    help="[sub] SELECT files from other file systems than the source one")
SELECTION_PARSER.add_argument(
    "--SELECT-regexp", action=SelectAction, metavar="REGEXP",
    help="[sub] SELECT files according to regexp pattern")
SELECTION_PARSER.add_argument(
    "--SELECT-if-present", action=SelectAction, metavar="FILENAME",
    help="[sub] SELECT directory if it contains the given file")
SELECTION_PARSER.add_argument(
    "--SELECT-special-files", action=SelectAction, type=bool, default=True,
    help="[sub] SELECT all device, fifo, socket files, and symbolic links")
SELECTION_PARSER.add_argument(
    "--max-file-size", action=SelectAction, metavar="SIZE", type=int,
    help="[sub] exclude files larger than given size in bytes")
SELECTION_PARSER.add_argument(
    "--min-file-size", action=SelectAction, metavar="SIZE", type=int,
    help="[sub] exclude files smaller than given size in bytes")

FILESYSTEM_PARSER = argparse.ArgumentParser(
    add_help=False,
    description="[parent] options related to file system capabilities")
FILESYSTEM_PARSER.add_argument(
    "--acls", default=True, action=BooleanOptionalAction,
    help="[sub] handle (or not) Access Control Lists")
FILESYSTEM_PARSER.add_argument(
    "--carbonfile", default=True, action=BooleanOptionalAction,
    help="[sub] handle (or not) carbon files on MacOS X")
FILESYSTEM_PARSER.add_argument(
    "--compare-inode", default=True, action=BooleanOptionalAction,
    help="[sub] compare (or not) inodes to decide if hard-linked files have changed")
FILESYSTEM_PARSER.add_argument(
    "--eas", default=True, action=BooleanOptionalAction,
    help="[sub] handle (or not) Extended Attributes")
FILESYSTEM_PARSER.add_argument(
    "--hard-links", default=True, action=BooleanOptionalAction,
    help="[sub] preserve (or not) hard links.")
FILESYSTEM_PARSER.add_argument(
    "--resource-forks", default=True, action=BooleanOptionalAction,
    help="[sub] preserve (or not) resource forks on MacOS X.")
FILESYSTEM_PARSER.add_argument(
    "--never-drop-acls", action="store_true",
    help="[sub] exit with error instead of dropping acls or acl entries.")

CREATION_PARSER = argparse.ArgumentParser(
    add_help=False,
    description="[parent] options related to creation of directories")
CREATION_PARSER.add_argument(
    "--create-full-path", action="store_true",
    help="[sub] create full necessary path to backup repository")

COMPRESSION_PARSER = argparse.ArgumentParser(
    add_help=False,
    description="[parent] options related to compression")
COMPRESSION_PARSER.add_argument(
    "--compression", default=True, action=BooleanOptionalAction,
    help="[sub] compress (or not) snapshot and diff files")
COMPRESSION_PARSER.add_argument(
    "--not-compressed-regexp", "--no-compression-regexp", metavar="REGEXP",
    default=DEFAULT_NOT_COMPRESSED_REGEXP,
    help="[sub] regexp to select files not being compressed")

STATISTICS_PARSER = argparse.ArgumentParser(
    add_help=False,
    description="[parent] options related to backup statistics")
STATISTICS_PARSER.add_argument(
    "--file-statistics", default=True, action=BooleanOptionalAction,
    help="[sub] do (or not) generate statistics file during backup")
STATISTICS_PARSER.add_argument(
    "--print-statistics", default=False, action=BooleanOptionalAction,
    help="[sub] print (or not) statistics after a successful backup")

TIMESTAMP_PARSER = argparse.ArgumentParser(
    add_help=False,
    description="[parent] options related to regress timestamps")
TIMESTAMP_PARSER.add_argument(
    "--allow-duplicate-timestamps", action="store_true",
    help="[sub] ignore duplicate metadata while checking repository")

USER_GROUP_PARSER = argparse.ArgumentParser(
    add_help=False,
    description="[parent] options related to user and group mapping")
USER_GROUP_PARSER.add_argument(
    "--group-mapping-file", type=str, metavar="MAP_FILE",
    help="[sub] map groups according to file")
USER_GROUP_PARSER.add_argument(
    "--preserve-numerical-ids", action="store_true",
    help="[sub] preserve user and group IDs instead of names")
USER_GROUP_PARSER.add_argument(
    "--user-mapping-file", type=str, metavar="MAP_FILE",
    help="[sub] map users according to file")

GENERIC_PARSERS = [COMMON_PARSER]
PARENT_PARSERS = [
    COMMON_COMPAT200_PARSER,  # compat200
    CREATION_PARSER, COMPRESSION_PARSER, SELECTION_PARSER,
    FILESYSTEM_PARSER, USER_GROUP_PARSER, STATISTICS_PARSER,
    TIMESTAMP_PARSER
]


class BaseAction:
    """
    Base rdiff-backup Action, and is to be used as base class for all these actions.
    """

    # name of the action as a string
    name = None

    # version of the action
    __version__ = "0.0.0"

    # list of parent parsers
    parent_parsers = []

    @classmethod
    def get_name(cls):
        return cls.name

    @classmethod
    def get_version(cls):
        return cls.__version__

    @classmethod
    def add_action_subparser(cls, sub_handler):
        """
        Given a subparsers handle as returned by argparse.add_subparsers,
        creates the subparser corresponding to the current Action class
        (as inherited).
        Most Action classes will need to extend this function with their
        own subparsers.
        Returns the computed subparser.
        """
        subparser = sub_handler.add_parser(cls.name,
                                           parents=cls.parent_parsers,
                                           description=cls.__doc__)
        subparser.set_defaults(action=cls.name)  # TODO cls instead of name!

        return subparser

    @classmethod
    def _get_subparsers(cls, parser, sub_dest, *sub_names):
        """
        This method can be used to add 2nd level subparsers to the action
        subparser (named here parser). sub_dest would typically be the name
        of the action, and sub_names are the names for the sub-subparsers.
        Returns the computed subparsers as dictionary with the sub_names as
        keys, so that arguments can be added to those subparsers as values.
        """
        if sys.version_info.major >= 3 and sys.version_info.minor >= 7:
            sub_handler = parser.add_subparsers(
                title="possible {dest}s".format(dest=sub_dest),
                required=True, dest=sub_dest)
        else:  # required didn't exist in Python 3.6
            sub_handler = parser.add_subparsers(
                title="possible {dest}s".format(dest=sub_dest),
                dest=sub_dest)

        subparsers = {}
        for sub_name in sub_names:
            subparsers[sub_name] = sub_handler.add_parser(sub_name)
            subparsers[sub_name].set_defaults(**{sub_dest: sub_name})
        return subparsers

    def __init__(self, values):
        """
        Dummy initialization method
        """
        self.values = values

    def print_values(self, explicit=True):
        """
        Dummy output method
        """
        print(yaml.safe_dump(self.values.__dict__,
                             explicit_start=explicit, explicit_end=explicit))


def get_action_class():
    return BaseAction
