#! /usr/bin/env python

"""Londiste setup and sanity checker.
"""

import sys, os, skytools

import pgq.setadmin

__all__ = ['LondisteSetup']

class LondisteSetup(pgq.setadmin.SetAdmin):
    initial_db_name = 'node_db'
    extra_objs = [ skytools.DBSchema("londiste", sql_file="londiste.sql") ]
    def __init__(self, args):
        pgq.setadmin.SetAdmin.__init__(self, 'londiste', args)
        self.set_name = self.cf.get("set_name")

    def init_optparse(self, parser=None):
        p = pgq.setadmin.SetAdmin.init_optparse(self, parser)
        p.add_option("--expect-sync", action="store_true", dest="expect_sync",
                    help = "no copy needed", default=False)
        p.add_option("--skip-truncate", action="store_true", dest="skip_truncate",
                    help = "dont delete old data", default=False)
        p.add_option("--force", action="store_true",
                    help="force", default=False)
        p.add_option("--all", action="store_true",
                    help="include all tables", default=False)
        return p

    def extra_init(self, node_type, node_db, provider_db):
        if not provider_db:
            return
        pcurs = provider_db.cursor()
        ncurs = node_db.cursor()
        q = "select table_name from londiste.set_get_table_list(%s)"
        pcurs.execute(q, [self.set_name])
        for row in pcurs.fetchall():
            tbl = row['table_name']
            q = "select * from londiste.set_add_table(%s, %s)"
            ncurs.execute(q, [self.set_name, tbl])
        node_db.commit()
        provider_db.commit()

    def cmd_add(self, *args):
        q = "select * from londiste.node_add_table(%s, %s)"
        db = self.get_database('node_db')
        self.exec_cmd_many(db, q, [self.set_name], args)

    def cmd_remove(self, *args):
        q = "select * from londiste.node_remove_table(%s, %s)"
        db = self.get_database('node_db')
        self.exec_cmd_many(db, q, [self.set_name], args)

    def cmd_add_seq(self, *args):
        q = "select * from londiste.node_add_seq(%s, %s)"
        db = self.get_database('node_db')
        self.exec_cmd_many(db, q, [self.set_name], args)

    def cmd_remove_seq(self, *args):
        q = "select * from londiste.node_remove_seq(%s, %s)"
        db = self.get_database('node_db')
        self.exec_cmd_many(db, q, [self.set_name], args)

    def cmd_resync(self, *args):
        q = "select * from londiste.node_resync_table(%s, %s)"
        db = self.get_database('node_db')
        self.exec_cmd_many(db, q, [self.set_name], args)

    def cmd_tables(self):
        q = "select table_name, merge_state from londiste.node_get_table_list(%s)"
        db = self.get_database('node_db')
        self.db_display_table(db, "Tables on node", q, [self.set_name])

    def cmd_seqs(self):
        q = "select seq_namefrom londiste.node_get_seq_list(%s)"
        db = self.get_database('node_db')
        self.db_display_table(db, "Sequences on node", q, [self.set_name])

    def cmd_missing(self):
        q = "select * from londiste.node_show_missing(%s)"
        db = self.get_database('node_db')
        self.db_display_table(db, "Missing objects on node", q, [self.set_name])

    def cmd_check(self):
        pass
    def cmd_fkeys(self):
        pass
    def cmd_triggers(self):
        pass

#
# Old commands
#

class LondisteSetup_tmp:

    def find_missing_provider_tables(self, pattern='*'):
        src_db = self.get_database('provider_db')
        src_curs = src_db.cursor()
        q = """select schemaname || '.' || tablename as full_name from pg_tables
                where schemaname not in ('pgq', 'londiste', 'pg_catalog', 'information_schema')
                  and schemaname !~ 'pg_.*'
                  and (schemaname || '.' || tablename) ~ %s
                except select table_name from londiste.provider_get_table_list(%s)"""
        src_curs.execute(q, [glob2regex(pattern), self.pgq_queue_name])
        rows = src_curs.fetchall()
        src_db.commit()
        list = []
        for row in rows:
            list.append(row[0])
        return list
                
    def admin(self):
        cmd = self.args[2]
        if cmd == "tables":
            self.subscriber_show_tables()
        elif cmd == "missing":
            self.subscriber_missing_tables()
        elif cmd == "add":
            self.subscriber_add_tables(self.args[3:])
        elif cmd == "remove":
            self.subscriber_remove_tables(self.args[3:])
        elif cmd == "resync":
            self.subscriber_resync_tables(self.args[3:])
        elif cmd == "register":
            self.subscriber_register()
        elif cmd == "unregister":
            self.subscriber_unregister()
        elif cmd == "install":
            self.subscriber_install()
        elif cmd == "check":
            self.check_tables(self.get_provider_table_list())
        elif cmd in ["fkeys", "triggers"]:
            self.collect_meta(self.get_provider_table_list(), cmd, self.args[3:])
        elif cmd == "seqs":
            self.subscriber_list_seqs()
        elif cmd == "add-seq":
            self.subscriber_add_seq(self.args[3:])
        elif cmd == "remove-seq":
            self.subscriber_remove_seq(self.args[3:])
        elif cmd == "restore-triggers":
            self.restore_triggers(self.args[3], self.args[4:])
        else:
            self.log.error('bad subcommand: ' + cmd)
            sys.exit(1)

    def collect_meta(self, table_list, meta, args):
        """Display fkey/trigger info."""

        if args == []:
            args = ['pending', 'active']
            
        field_map = {'triggers': ['table_name', 'trigger_name', 'trigger_def'],
                     'fkeys': ['from_table', 'to_table', 'fkey_name', 'fkey_def']}
        
        query_map = {'pending': "select %s from londiste.subscriber_get_table_pending_%s(%%s)",
                     'active' : "select %s from londiste.find_table_%s(%%s)"}

        table_list = self.clean_subscriber_tables(table_list)
        if len(table_list) == 0:
            self.log.info("No tables, no fkeys")
            return

        dst_db = self.get_database('subscriber_db')
        dst_curs = dst_db.cursor()

        for which in args:
            union_list = []
            fields = field_map[meta]
            q = query_map[which] % (",".join(fields), meta)
            for tbl in table_list:
                union_list.append(q % skytools.quote_literal(tbl))

            # use union as fkey may appear in duplicate
            sql = " union ".join(union_list) + " order by 1"
            desc = "%s %s" % (which, meta)
            self.display_table(desc, dst_curs, fields, sql)
        dst_db.commit()

    def check_tables(self, table_list):
        src_db = self.get_database('provider_db')
        src_curs = src_db.cursor()
        dst_db = self.get_database('subscriber_db')
        dst_curs = dst_db.cursor()

        failed = 0
        for tbl in table_list:
            self.log.info('Checking %s' % tbl)
            if not skytools.exists_table(src_curs, tbl):
                self.log.error('Table %s missing from provider side' % tbl)
                failed += 1
            elif not skytools.exists_table(dst_curs, tbl):
                self.log.error('Table %s missing from subscriber side' % tbl)
                failed += 1
            else:
                failed += self.check_table_columns(src_curs, dst_curs, tbl)

        src_db.commit()
        dst_db.commit()

        return failed

    def restore_triggers(self, tbl, triggers=None):
        tbl = skytools.fq_name(tbl)
        if tbl not in self.get_subscriber_table_list():
            self.log.error("Table %s is not in the subscriber queue." % tbl)
            sys.exit(1)
            
        dst_db = self.get_database('subscriber_db')
        dst_curs = dst_db.cursor()
        
        if not triggers:
            q = "select count(1) from londiste.subscriber_get_table_pending_triggers(%s)"
            dst_curs.execute(q, [tbl])
            if not dst_curs.fetchone()[0]:
                self.log.info("No pending triggers found for %s." % tbl)
            else:
                q = "select londiste.subscriber_restore_all_table_triggers(%s)"
                dst_curs.execute(q, [tbl])
        else:
            for trigger in triggers:
                q = "select count(1) from londiste.find_table_triggers(%s) where trigger_name=%s"
                dst_curs.execute(q, [tbl, trigger])
                if dst_curs.fetchone()[0]:
                    self.log.info("Trigger %s on %s is already active." % (trigger, tbl))
                    continue
                    
                q = "select count(1) from londiste.subscriber_get_table_pending_triggers(%s) where trigger_name=%s"
                dst_curs.execute(q, [tbl, trigger])
                if not dst_curs.fetchone()[0]:
                    self.log.info("Trigger %s not found on %s" % (trigger, tbl))
                    continue
                    
                q = "select londiste.subscriber_restore_table_trigger(%s, %s)"
                dst_curs.execute(q, [tbl, trigger])
        dst_db.commit()

    def check_table_columns(self, src_curs, dst_curs, tbl):
        src_colrows = find_column_types(src_curs, tbl)
        dst_colrows = find_column_types(dst_curs, tbl)

        src_cols = make_type_string(src_colrows)
        dst_cols = make_type_string(dst_colrows)
        if src_cols.find('k') < 0:
            self.log.error('provider table %s has no primary key (%s)' % (
                             tbl, src_cols))
            return 1
        if dst_cols.find('k') < 0:
            self.log.error('subscriber table %s has no primary key (%s)' % (
                             tbl, dst_cols))
            return 1

        if src_cols != dst_cols:
            self.log.warning('table %s structure is not same (%s/%s)'\
                 ', trying to continue' % (tbl, src_cols, dst_cols))

        err = 0
        for row in src_colrows:
            found = 0
            for row2 in dst_colrows:
                if row2['name'] == row['name']:
                    found = 1
                    break
            if not found:
                err = 1
                self.log.error('%s: column %s on provider not on subscriber'
                                    % (tbl, row['name']))
            elif row['type'] != row2['type']:
                err = 1
                self.log.error('%s: pk different on column %s'
                                    % (tbl, row['name']))

        return err

    def find_missing_subscriber_tables(self, pattern='*'):
        src_db = self.get_database('subscriber_db')
        src_curs = src_db.cursor()
        q = """select schemaname || '.' || tablename as full_name from pg_tables
                where schemaname not in ('pgq', 'londiste', 'pg_catalog', 'information_schema')
                  and schemaname !~ 'pg_.*'
                  and schemaname || '.' || tablename ~ %s
                except select table_name from londiste.provider_get_table_list(%s)"""
        src_curs.execute(q, [glob2regex(pattern), self.pgq_queue_name])
        rows = src_curs.fetchall()
        src_db.commit()
        list = []
        for row in rows:
            list.append(row[0])
        return list

