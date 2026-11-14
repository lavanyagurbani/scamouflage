"""Initialize or explicitly check/reset a local admin; never accept a password argument."""
import argparse
import getpass
import logging
import os
import sys
import warnings


def password_matches(user, password):
    from werkzeug.security import check_password_hash
    return check_password_hash(user.password, password)


def manage_user(manager, username, password, mode):
    user = manager.find_user(username=username)
    if mode != 'initialize':
        if not user:
            print('FAIL: requested user does not exist; no user created.')
            return 1
        if not user.is_active or not any(role.name == 'Admin' for role in user.roles):
            print('FAIL: account is inactive or lacks the Admin role; no account/role changes made.')
            return 1
        if mode == 'reset':
            # Find and reset through the SAME security manager and Flask app.
            # Keep the supported API's session invalidation; do not monkey-patch it.
            if not manager.reset_password(user.id, password):
                print('FAIL: FAB did not complete the password reset. Check the stored password separately.')
                return 1
            manager.get_session.expire_all()
            user = manager.find_user(username=username)
        if not user or not password_matches(user, password):
            print('FAIL: supplied password does not match the stored hash.')
            return 1
        print('PASS: stored password matches; account is active with Admin role. Browser login remains to be verified.')
        return 0
    if user:
        print('Local admin already exists; password left unchanged.')
        return 0
    user = manager.add_user(username=username, first_name='Local', last_name='Admin',
                            email='admin@localhost.invalid', role=manager.find_role('Admin'), password=password)
    if not user:
        print('FAIL: local admin creation failed.')
        return 1
    print('Local admin created; no cloud work performed.')
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--reset-password', action='store_true', help='Explicitly reset an existing active admin using hidden prompts')
    modes.add_argument('--check-password', action='store_true', help='Compare hidden input to stored hash without resetting or logging in')
    parser.add_argument('--username', default=os.environ.get('AIRFLOW_ADMIN_USERNAME', 'admin'))
    args = parser.parse_args(argv)
    mode = 'reset' if args.reset_password else 'check' if args.check_password else 'initialize'
    previous_logging = logging.root.manager.disable
    try:
        if mode == 'initialize':
            password = os.environ.get('AIRFLOW_ADMIN_PASSWORD', '')
            secret = os.environ.get('AIRFLOW__WEBSERVER__SECRET_KEY', '')
            if not password or password == 'CHANGE_ME_PASSWORD' or not secret or secret == 'CHANGE_ME_SECRET':
                print('FAIL: set local admin password and webserver secret before initialization.')
                return 1
        else:
            if not sys.stdin.isatty():
                print('FAIL: use an interactive terminal; passwords cannot be supplied by pipe or argument.')
                return 1
            with warnings.catch_warnings():
                # Refuse getpass's echoing fallback if a usable terminal is absent.
                warnings.simplefilter('error', getpass.GetPassWarning)
                password = getpass.getpass('New password: ' if mode == 'reset' else 'Password to check: ')
                if not password:
                    print('CANCELLED: empty password; no change made.')
                    return 1
                if mode == 'reset' and password != getpass.getpass('Repeat new password: '):
                    print('CANCELLED: passwords did not match; no change made.')
                    return 1
        # Avoid ORM/FAB exception logs containing SQL parameters or password hashes.
        # Failures are reported explicitly below, without raw exception payloads.
        logging.disable(logging.CRITICAL)
        from airflow.www.app import cached_app
        app = cached_app()  # Exactly one application, initialized once in this process.
        with app.app_context():
            try:
                return manage_user(app.appbuilder.sm, args.username, password, mode)
            except BaseException:
                app.appbuilder.sm.get_session.rollback()
                raise
    except (EOFError, KeyboardInterrupt, getpass.GetPassWarning):
        print('CANCELLED: hidden terminal input unavailable or interrupted; verify stored state if reset started.')
        return 1
    except Exception as exc:
        print(f'FAIL: local admin operation failed ({type(exc).__name__}). No raw error or credential values displayed.')
        print('A reset may be incomplete; use --check-password in a fresh process before assuming it succeeded.')
        return 1
    finally:
        logging.disable(previous_logging)


if __name__ == '__main__':
    sys.exit(main())
