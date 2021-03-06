
create or replace function pgq_set.add_member(
    in i_set_name text,
    in i_node_name text,
    in i_node_location text,
    in i_dead boolean,
    out ret_code int4,
    out ret_note text)
returns record as $$
-- ----------------------------------------------------------------------
-- Function: pgq_set.add_member(3)
--
--      Add new set member.
--
-- Parameters:
--      i_set_name - set name
--      i_node_name - node name
--      i_node_location - node connect string
--      i_dead - dead flag for node
--
-- Returns:
--      ret_code - error code
--      ret_note - error description
--
-- Return Codes:
--      200 - Ok
--      404 - No such set
-- ----------------------------------------------------------------------
declare
    o  record;
    node record;
begin
    select node_type in ('root', 'combined-root') as is_root
      into node
      from pgq_set.set_info where set_name = i_set_name
       for update;

    select node_location into o
      from pgq_set.member_info
     where set_name = i_set_name
       and node_name = i_node_name;
    if found then
        update pgq_set.member_info
           set node_location = i_node_location,
               dead = i_dead
         where set_name = i_set_name
           and node_name = i_node_name;
    else
        insert into pgq_set.member_info (set_name, node_name, node_location, dead)
        values (i_set_name, i_node_name, i_node_location, i_dead);
    end if;

    if node.is_root then
        perform pgq.insert_event(s.queue_name, 'member-info',
                                 i_node_name, i_set_name, i_node_location, i_dead::text, null)
           from pgq_set.set_info s
         where s.set_name = i_set_name;
    end if;

    select 100, 'Ok' into ret_code, ret_note;
    return;
end;
$$ language plpgsql security definer;

