
create or replace function londiste.node_set_table_state(
    i_set_name text,
    i_table_name text,
    i_snapshot text,
    i_merge_state text)
returns integer as $$
-- ----------------------------------------------------------------------
-- Function: londiste.node_set_table_state(4)
--
--      Change table state.
--
-- Parameters:
--      i_set_name      - set name
--      i-table         - table name
--      i_snapshot      - optional remote snapshot info
--      i_merge_state   - merge state
--
-- Returns:
--      nothing
-- ----------------------------------------------------------------------
begin
    update londiste.node_table
        set custom_snapshot = i_snapshot,
            merge_state = i_merge_state,
            -- reset skip_snapshot when table is copied over
            skip_truncate = case when i_merge_state = 'ok'
                                 then null
                                 else skip_truncate
                            end
      where set_name = i_set_name
        and table_name = i_table_name;
    if not found then
        raise exception 'no such table';
    end if;

    return 1;
end;
$$ language plpgsql;

