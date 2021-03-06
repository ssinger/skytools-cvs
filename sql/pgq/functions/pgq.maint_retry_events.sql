create or replace function pgq.maint_retry_events()
returns integer as $$
-- ----------------------------------------------------------------------
-- Function: pgq.maint_retry_events(0)
--
--      Moves retry events back to main queue.
--
--      It moves small amount at a time.  It should be called
--      until it returns 0
--
-- Parameters:
--      arg - desc
--
-- Returns:
--      Number of events processed.
-- ----------------------------------------------------------------------
declare
    cnt    integer;
    rec    record;
begin
    cnt := 0;
    for rec in
        select pgq.insert_event_raw(queue_name,
                    ev_id, ev_time, ev_owner, ev_retry, ev_type, ev_data,
                    ev_extra1, ev_extra2, ev_extra3, ev_extra4),
               ev_owner, ev_id
          from pgq.retry_queue, pgq.queue, pgq.subscription
         where ev_retry_after <= current_timestamp
           and sub_id = ev_owner
           and queue_id = sub_queue
         order by ev_retry_after
         limit 10
    loop
        cnt := cnt + 1;
        delete from pgq.retry_queue
         where ev_owner = rec.ev_owner
           and ev_id = rec.ev_id;
    end loop;
    return cnt;
end;
$$ language plpgsql; -- need admin access

