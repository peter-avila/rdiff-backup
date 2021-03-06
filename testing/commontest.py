"""commontest - Some functions and constants common to several test cases.
Can be called also directly to setup the test environment"""
import os
import sys
import code
import shutil
import subprocess
# Avoid circularities
from rdiff_backup.log import Log
from rdiff_backup import Globals, Hardlink, SetConnections, Main, \
    selection, rpath, eas_acls, rorpiter, Security, hash
from rdiffbackup import arguments

RBBin = os.fsencode(shutil.which("rdiff-backup") or "rdiff-backup")

# Working directory is defined by Tox, venv or the current build directory
abs_work_dir = os.fsencode(os.getenv(
    'TOX_ENV_DIR',
    os.getenv('VIRTUAL_ENV', os.path.join(os.getcwd(), 'build'))))
abs_test_dir = os.path.join(abs_work_dir, b'testfiles')
abs_output_dir = os.path.join(abs_test_dir, b'output')
abs_restore_dir = os.path.join(abs_test_dir, b'restore')

# the directory with the testfiles used as input is in the parent directory of the Git clone
old_test_dir = os.path.join(os.path.dirname(os.getcwdb()),
                            b'rdiff-backup_testfiles')
old_inc1_dir = os.path.join(old_test_dir, b'increment1')
old_inc2_dir = os.path.join(old_test_dir, b'increment2')
old_inc3_dir = os.path.join(old_test_dir, b'increment3')
old_inc4_dir = os.path.join(old_test_dir, b'increment4')

# the directory in which all testing scripts are placed is the one
abs_testing_dir = os.path.dirname(os.path.abspath(os.fsencode(sys.argv[0])))

__no_execute__ = 1  # Keeps the actual rdiff-backup program from running


def Myrm(dirstring):
    """Run myrm on given directory string"""
    root_rp = rpath.RPath(Globals.local_connection, dirstring)
    for rp in selection.Select(root_rp).set_iter():
        if rp.isdir():
            rp.chmod(0o700)  # otherwise may not be able to remove
    path = root_rp.path
    if os.path.isdir(path):
        shutil.rmtree(path)
    elif os.path.isfile(path):
        os.remove(path)


def re_init_rpath_dir(rp, uid=-1, gid=-1):
    """Delete directory if present, then recreate"""
    if rp.lstat():
        Myrm(rp.path)
        rp.setdata()
    rp.mkdir()
    rp.chown(uid, gid)


def re_init_subdir(maindir, subdir):
    """Remove a sub-directory and return its name joined
    to the main directory as an empty directory"""
    dir = os.path.join(maindir, subdir)
    Myrm(dir)
    os.makedirs(dir)
    return dir


# two temporary directories to simulate remote actions
abs_remote1_dir = re_init_subdir(abs_test_dir, b'remote1')
abs_remote2_dir = re_init_subdir(abs_test_dir, b'remote2')


def MakeOutputDir():
    """Initialize the output directory"""
    Myrm(abs_output_dir)
    rp = rpath.RPath(Globals.local_connection, abs_output_dir)
    rp.mkdir()
    return rp


def rdiff_backup(source_local,
                 dest_local,
                 src_dir,
                 dest_dir,
                 current_time=None,
                 extra_options=b"",
                 input=None,
                 check_return_val=1,
                 expected_ret_val=0):
    """Run rdiff-backup with the given options

    source_local and dest_local are boolean values.  If either is
    false, then rdiff-backup will be run pretending that src_dir and
    dest_dir, respectively, are remote.  The server process will be
    run in directories remote1 and remote2 respectively.

    src_dir and dest_dir are the source and destination
    (mirror) directories, relative to the testing directory.

    If current time is true, add the --current-time option with the
    given number of seconds.

    extra_options are just added to the command line.

    """
    if not source_local:
        src_dir = (b"'cd %s; %s --server'::%s" %
                   (abs_remote1_dir, RBBin, src_dir))
    if dest_dir and not dest_local:
        dest_dir = (b"'cd %s; %s --server'::%s" %
                    (abs_remote2_dir, RBBin, dest_dir))

    cmdargs = [RBBin, extra_options]
    if not (source_local and dest_local):
        cmdargs.append(b"--remote-schema {h}")

    if current_time:
        cmdargs.append(b"--current-time %i" % current_time)
    cmdargs.append(src_dir)
    if dest_dir:
        cmdargs.append(dest_dir)
    cmdline = b" ".join(cmdargs)
    print("Executing: ", cmdline)
    ret_val = subprocess.run(cmdline,
                             shell=True,
                             input=input,
                             universal_newlines=False).returncode
    if check_return_val:
        # the construct is needed because os.system seemingly doesn't
        # respect expected return values (FIXME)
        assert ((expected_ret_val == 0 and ret_val == 0) or (expected_ret_val > 0 and ret_val > 0)), \
            "Return code %d of command `%a` isn't as expected %d." % \
            (ret_val, cmdline, expected_ret_val)
    return ret_val


def _internal_get_cmd_pairs(src_local, dest_local, src_dir, dest_dir):
    """Function returns a tuple of connections based on the given parameters.
    One or both directories are faked for remote connection if not local,
    and the connections are set accordingly.
    Note that the function relies on the global variables
    abs_remote1_dir, abs_remote2_dir and abs_testing_dir."""

    remote_schema = b'%s'  # compat200: replace with {h}
    remote_format = b"cd %s; %s/server.py::%s"

    if not src_local:
        src_dir = remote_format % (abs_remote1_dir, abs_testing_dir, src_dir)
    if not dest_local:
        dest_dir = remote_format % (abs_remote2_dir, abs_testing_dir, dest_dir)

    if src_local and dest_local:
        return SetConnections.get_cmd_pairs([src_dir, dest_dir])
    else:
        return SetConnections.get_cmd_pairs([src_dir, dest_dir], remote_schema)


def InternalBackup(source_local,
                   dest_local,
                   src_dir,
                   dest_dir,
                   current_time=None,
                   eas=None,
                   acls=None):
    """Backup src to dest internally

    This is like rdiff_backup but instead of running a separate
    rdiff-backup script, use the separate *.py files.  This way the
    script doesn't have to be rebuild constantly, and stacktraces have
    correct line/file references.

    """
    Globals.current_time = current_time
    Globals.security_level = "override"
    Globals.set("no_compression_regexp_string",
                os.fsencode(arguments.DEFAULT_NOT_COMPRESSED_REGEXP))

    cmdpairs = _internal_get_cmd_pairs(source_local, dest_local,
                                       src_dir, dest_dir)

    Security.initialize("backup", cmdpairs)
    rpin, rpout = list(map(SetConnections.cmdpair2rp, cmdpairs))
    for attr in ('eas_active', 'eas_write', 'eas_conn'):
        SetConnections.UpdateGlobal(attr, eas)
    for attr in ('acls_active', 'acls_write', 'acls_conn'):
        SetConnections.UpdateGlobal(attr, acls)
    Main._misc_setup([rpin, rpout])
    Main._action_backup(rpin, rpout)
    Main._cleanup()


def InternalMirror(source_local, dest_local, src_dir, dest_dir):
    """Mirror src to dest internally

    like InternalBackup, but only mirror.  Do this through
    InternalBackup, but then delete rdiff-backup-data directory.

    """
    # Save attributes of root to restore later
    src_root = rpath.RPath(Globals.local_connection, src_dir)
    dest_root = rpath.RPath(Globals.local_connection, dest_dir)
    dest_rbdir = dest_root.append("rdiff-backup-data")

    InternalBackup(source_local, dest_local, src_dir, dest_dir)
    dest_root.setdata()
    Myrm(dest_rbdir.path)
    # Restore old attributes
    rpath.copy_attribs(src_root, dest_root)


def InternalRestore(mirror_local,
                    dest_local,
                    mirror_dir,
                    dest_dir,
                    time,
                    eas=None,
                    acls=None):
    """Restore mirror_dir to dest_dir at given time

    This will automatically find the increments.XXX.dir representing
    the time specified.  The mirror_dir and dest_dir are relative to
    the testing directory and will be modified for remote trials.

    """
    Main._force = 1
    Main._restore_root_set = 0
    Globals.security_level = "override"
    Globals.set("no_compression_regexp_string",
                os.fsencode(arguments.DEFAULT_NOT_COMPRESSED_REGEXP))

    cmdpairs = _internal_get_cmd_pairs(mirror_local, dest_local,
                                       mirror_dir, dest_dir)

    Security.initialize("restore", cmdpairs)
    mirror_rp, dest_rp = list(map(SetConnections.cmdpair2rp, cmdpairs))
    for attr in ('eas_active', 'eas_write', 'eas_conn'):
        SetConnections.UpdateGlobal(attr, eas)
    for attr in ('acls_active', 'acls_write', 'acls_conn'):
        SetConnections.UpdateGlobal(attr, acls)
    Main._misc_setup([mirror_rp, dest_rp])
    inc = get_increment_rp(mirror_rp, time)
    if inc:
        Main._restore_timestr = None
        Main._action_restore(get_increment_rp(mirror_rp, time), dest_rp)
    else:  # use alternate syntax
        Main._restore_timestr = str(time)
        Main._action_restore(mirror_rp, dest_rp)
    Main._cleanup()


def get_increment_rp(mirror_rp, time):
    """Return increment rp matching time in seconds"""
    data_rp = mirror_rp.append("rdiff-backup-data")
    if not data_rp.isdir():
        return None
    for filename in data_rp.listdir():
        rp = data_rp.append(filename)
        if rp.isincfile() and rp.getincbase_bname() == b"increments":
            if rp.getinctime() == time:
                return rp
    return None  # Couldn't find appropriate increment


def _reset_connections(src_rp, dest_rp):
    """Reset some global connection information"""
    Globals.security_level = "override"
    Globals.isbackup_reader = Globals.isbackup_writer = None
    SetConnections.UpdateGlobal('rbdir', None)
    Main._misc_setup([src_rp, dest_rp])


def _hardlink_rorp_eq(src_rorp, dest_rorp):
    """Compare two files for hardlink equality, encompassing being hard-linked,
    having the same hashsum, and the same number of link counts."""
    Hardlink.add_rorp(dest_rorp)
    Hardlink.add_rorp(src_rorp, dest_rorp)
    rorp_eq = Hardlink.rorp_eq(src_rorp, dest_rorp)
    if not src_rorp.isreg() or not dest_rorp.isreg() or src_rorp.getnumlinks() == dest_rorp.getnumlinks() == 1:
        if not rorp_eq:
            Log("Hardlink compare error with when no links exist", 3)
            Log("%s: %s" % (src_rorp.index, Hardlink._get_inode_key(src_rorp)), 3)
            Log("%s: %s" % (dest_rorp.index, Hardlink._get_inode_key(dest_rorp)), 3)
            return False
    elif src_rorp.getnumlinks() > 1 and not Hardlink.is_linked(src_rorp):
        if rorp_eq:
            Log("Hardlink compare error with first linked src_rorp and no dest_rorp sha1", 3)
            Log("%s: %s" % (src_rorp.index, Hardlink._get_inode_key(src_rorp)), 3)
            Log("%s: %s" % (dest_rorp.index, Hardlink._get_inode_key(dest_rorp)), 3)
            return False
        hash.compute_sha1(dest_rorp)
        rorp_eq = Hardlink.rorp_eq(src_rorp, dest_rorp)
        if src_rorp.getnumlinks() != dest_rorp.getnumlinks():
            if rorp_eq:
                Log("Hardlink compare error with first linked src_rorp, with dest_rorp sha1, and with differing link counts", 3)
                Log("%s: %s" % (src_rorp.index, Hardlink._get_inode_key(src_rorp)), 3)
                Log("%s: %s" % (dest_rorp.index, Hardlink._get_inode_key(dest_rorp)), 3)
                return False
        elif not rorp_eq:
            Log("Hardlink compare error with first linked src_rorp, with dest_rorp sha1, and with equal link counts", 3)
            Log("%s: %s" % (src_rorp.index, Hardlink._get_inode_key(src_rorp)), 3)
            Log("%s: %s" % (dest_rorp.index, Hardlink._get_inode_key(dest_rorp)), 3)
            return False
    elif src_rorp.getnumlinks() != dest_rorp.getnumlinks():
        if rorp_eq:
            Log("Hardlink compare error with non-first linked src_rorp and with differing link counts", 3)
            Log("%s: %s" % (src_rorp.index, Hardlink._get_inode_key(src_rorp)), 3)
            Log("%s: %s" % (dest_rorp.index, Hardlink._get_inode_key(dest_rorp)), 3)
            return False
    elif not rorp_eq:
        Log("Hardlink compare error with non-first linked src_rorp and with equal link counts", 3)
        Log("%s: %s" % (src_rorp.index, Hardlink._get_inode_key(src_rorp)), 3)
        Log("%s: %s" % (dest_rorp.index, Hardlink._get_inode_key(dest_rorp)), 3)
        return False
    Hardlink.del_rorp(src_rorp)
    Hardlink.del_rorp(dest_rorp)
    return True


def _ea_compare_rps(rp1, rp2):
    """Return true if rp1 and rp2 have same extended attributes."""
    ea1 = eas_acls.ExtendedAttributes(rp1.index)
    ea1.read_from_rp(rp1)
    ea2 = eas_acls.ExtendedAttributes(rp2.index)
    ea2.read_from_rp(rp2)
    return ea1 == ea2


def _acl_compare_rps(rp1, rp2):
    """Return true if rp1 and rp2 have same acl information."""
    acl1 = eas_acls.AccessControlLists(rp1.index)
    acl1.read_from_rp(rp1)
    acl2 = eas_acls.AccessControlLists(rp2.index)
    acl2.read_from_rp(rp2)
    return acl1 == acl2


def _files_rorp_eq(src_rorp, dest_rorp,
                   compare_hardlinks=True,
                   compare_ownership=False,
                   compare_eas=False,
                   compare_acls=False):
    """Combined eq func returns true if two files compare same"""
    if not src_rorp:
        Log("Source rorp missing: %s" % str(dest_rorp), 3)
        return False
    if not dest_rorp:
        Log("Dest rorp missing: %s" % str(src_rorp), 3)
        return False
    if not src_rorp._equal_verbose(dest_rorp,
                                   compare_ownership=compare_ownership):
        return False
    if compare_hardlinks and not _hardlink_rorp_eq(src_rorp, dest_rorp):
        return False
    if compare_eas and not _ea_compare_rps(src_rorp, dest_rorp):
        Log(
            "Different EAs in files %s and %s" %
            (src_rorp.get_indexpath(), dest_rorp.get_indexpath()), 3)
        return False
    if compare_acls and not _acl_compare_rps(src_rorp, dest_rorp):
        Log(
            "Different ACLs in files %s and %s" %
            (src_rorp.get_indexpath(), dest_rorp.get_indexpath()), 3)
        return False
    return True


def _get_selection_functions(src_rp, dest_rp,
                             exclude_rbdir=True,
                             ignore_tmp_files=False):
    """Return generators of files in source, dest"""
    src_rp.setdata()
    dest_rp.setdata()
    src_select = selection.Select(src_rp)
    dest_select = selection.Select(dest_rp)

    if ignore_tmp_files:
        # Ignoring temp files can be useful when we want to check the
        # correctness of a backup which aborted in the middle.  In
        # these cases it is OK to have tmp files lying around.
        src_select._add_selection_func(
            src_select._regexp_get_sf(".*rdiff-backup.tmp.[^/]+$", 0))
        dest_select._add_selection_func(
            dest_select._regexp_get_sf(".*rdiff-backup.tmp.[^/]+$", 0))

    if exclude_rbdir:  # Exclude rdiff-backup-data directory
        src_select.parse_rbdir_exclude()
        dest_select.parse_rbdir_exclude()

    return src_select.set_iter(), dest_select.set_iter()


def compare_recursive(src_rp, dest_rp,
                      compare_hardlinks=True,
                      exclude_rbdir=True,
                      ignore_tmp_files=False,
                      compare_ownership=False,
                      compare_eas=False,
                      compare_acls=False):
    """Compare src_rp and dest_rp, which can be directories

    This only compares file attributes, not the actual data.  This
    will overwrite the hardlink dictionaries if compare_hardlinks is
    specified.

    """

    Log(
        "Comparing %s and %s, hardlinks %s, eas %s, acls %s" %
        (src_rp.get_safepath(), dest_rp.get_safepath(), compare_hardlinks,
         compare_eas, compare_acls), 3)
    if compare_hardlinks:
        reset_hardlink_dicts()
    src_iter, dest_iter = _get_selection_functions(
        src_rp, dest_rp,
        exclude_rbdir=exclude_rbdir,
        ignore_tmp_files=ignore_tmp_files)
    for src_rorp, dest_rorp in rorpiter.Collate2Iters(src_iter, dest_iter):
        if not _files_rorp_eq(src_rorp, dest_rorp,
                              compare_hardlinks=compare_hardlinks,
                              compare_ownership=compare_ownership,
                              compare_eas=compare_eas,
                              compare_acls=compare_acls):
            return 0
    return 1


def reset_hardlink_dicts():
    """Clear the hardlink dictionaries"""
    Hardlink._inode_index = {}


def BackupRestoreSeries(source_local,
                        dest_local,
                        list_of_dirnames,
                        compare_hardlinks=1,
                        dest_dirname=abs_output_dir,
                        restore_dirname=abs_restore_dir,
                        compare_backups=1,
                        compare_eas=0,
                        compare_acls=0,
                        compare_ownership=0):
    """Test backing up/restoring of a series of directories

    The dirnames correspond to a single directory at different times.
    After each backup, the dest dir will be compared.  After the whole
    set, each of the earlier directories will be recovered to the
    restore_dirname and compared.

    """
    Globals.set('preserve_hardlinks', compare_hardlinks)
    Globals.set("no_compression_regexp_string",
                os.fsencode(arguments.DEFAULT_NOT_COMPRESSED_REGEXP))
    time = 10000
    dest_rp = rpath.RPath(Globals.local_connection, dest_dirname)
    restore_rp = rpath.RPath(Globals.local_connection, restore_dirname)

    Myrm(dest_dirname)
    for dirname in list_of_dirnames:
        src_rp = rpath.RPath(Globals.local_connection, dirname)
        reset_hardlink_dicts()
        _reset_connections(src_rp, dest_rp)

        InternalBackup(source_local,
                       dest_local,
                       dirname,
                       dest_dirname,
                       time,
                       eas=compare_eas,
                       acls=compare_acls)
        time += 10000
        _reset_connections(src_rp, dest_rp)
        if compare_backups:
            assert compare_recursive(src_rp,
                                     dest_rp,
                                     compare_hardlinks,
                                     compare_eas=compare_eas,
                                     compare_acls=compare_acls,
                                     compare_ownership=compare_ownership)

    time = 10000
    for dirname in list_of_dirnames[:-1]:
        reset_hardlink_dicts()
        Myrm(restore_dirname)
        InternalRestore(dest_local,
                        source_local,
                        dest_dirname,
                        restore_dirname,
                        time,
                        eas=compare_eas,
                        acls=compare_acls)
        src_rp = rpath.RPath(Globals.local_connection, dirname)
        assert compare_recursive(src_rp,
                                 restore_rp,
                                 compare_eas=compare_eas,
                                 compare_acls=compare_acls,
                                 compare_ownership=compare_ownership)

        # Restore should default back to newest time older than it
        # with a backup then.
        if time == 20000:
            time = 21000

        time += 10000


def MirrorTest(source_local,
               dest_local,
               list_of_dirnames,
               compare_hardlinks=1,
               dest_dirname=abs_output_dir):
    """Mirror each of list_of_dirnames, and compare after each"""
    Globals.set('preserve_hardlinks', compare_hardlinks)
    Globals.set("no_compression_regexp_string",
                os.fsencode(arguments.DEFAULT_NOT_COMPRESSED_REGEXP))
    dest_rp = rpath.RPath(Globals.local_connection, dest_dirname)
    old_force_val = Main._force
    Main._force = 1

    Myrm(dest_dirname)
    for dirname in list_of_dirnames:
        src_rp = rpath.RPath(Globals.local_connection, dirname)
        reset_hardlink_dicts()
        _reset_connections(src_rp, dest_rp)

        InternalMirror(source_local, dest_local, dirname, dest_dirname)
        _reset_connections(src_rp, dest_rp)
        assert compare_recursive(src_rp, dest_rp, compare_hardlinks)
    Main.force = old_force_val


def raise_interpreter(use_locals=None):
    """Start Python interpreter, with local variables if locals is true"""
    if use_locals:
        local_dict = locals()
    else:
        local_dict = globals()
    code.InteractiveConsole(local_dict).interact()


def getrefs(i, depth):
    """Get the i'th object in memory, return objects that reference it"""
    import sys
    import gc
    import types
    o = sys.getobjects(i)[-1]
    for d in range(depth):
        for ref in gc.get_referrers(o):
            if type(ref) in (list, dict, types.InstanceType):
                if type(ref) is dict and 'copyright' in ref:
                    continue
                o = ref
                break
        else:
            print("Max depth ", d)
            return o
    return o


def iter_equal(iter1, iter2, verbose=None, operator=lambda x, y: x == y):
    """True if iterator 1 has same elements as iterator 2

    Use equality operator, or == if it is unspecified.

    """
    for i1 in iter1:
        try:
            i2 = next(iter2)
        except StopIteration:
            if verbose:
                print("End when i1 = %s" % (i1, ))
            return False
        if not operator(i1, i2):
            if verbose:
                print("%s not equal to %s" % (i1, i2))
            return False
    try:
        i2 = next(iter2)
    except StopIteration:
        return True
    if verbose:
        print("End when i2 = %s" % (i2, ))
    return False


def iter_map(function, iterator):
    """Like map in a lazy functional programming language"""
    for i in iterator:
        yield function(i)


def xcopytree(source, dest, content=False):
    """copytree can't copy all kind of files but is platform independent
    hence we use it only if the 'cp' utility doesn't exist.
    If content is True then dest is created if needed and
    the content of the source is copied into dest and not source itself."""
    if content:
        subs = map(lambda d: os.path.join(source, d), os.listdir(source))
        os.makedirs(dest, exist_ok=True)
    else:
        subs = (source,)
    for sub in subs:
        if shutil.which('cp'):
            subprocess.run((b'cp', b'-a', sub, dest), check=True)
        else:
            shutil.copytree(sub, dest, symlinks=True)


if __name__ == '__main__':
    os.makedirs(abs_test_dir, exist_ok=True)
