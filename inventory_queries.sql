-- =============================================================================
-- Jira inventory queries for cleanup work
--
-- Every object in a Jira instance with: how many issues use it and when one of
-- those issues was last updated. Anything with zero issues, or no activity in
-- a year or more, goes on the cleanup list.
--
-- Read-only. Written for SQL Server. On PostgreSQL, quote the AO_ plugin
-- tables and their columns ("AO_60DB71_RAPIDVIEW"."NAME") and swap
-- CAST(... AS NVARCHAR) for CAST(... AS VARCHAR).
-- Run against a staging copy where you can.
-- =============================================================================


-- 1. Custom fields: issue count and last activity --------------------------------
SELECT  cf.id,
        cf.cfname                AS custom_field_name,
        cf.customfieldtypekey    AS field_type,
        COUNT(DISTINCT ji.id)    AS issue_count,
        MAX(ji.updated)          AS last_updated
FROM    customfield cf
LEFT JOIN customfieldvalue cfv ON cfv.customfield = cf.id
LEFT JOIN jiraissue ji         ON ji.id = cfv.issue
GROUP BY cf.id, cf.cfname, cf.customfieldtypekey
ORDER BY issue_count ASC, last_updated ASC;


-- 1b. Same, minus fields owned by Jira Software, Service Management, Capture and
--     Portfolio. Those are system fields you shouldn't delete anyway.
SELECT  cf.id,
        cf.cfname                AS custom_field_name,
        cf.customfieldtypekey    AS field_type,
        COUNT(DISTINCT ji.id)    AS issue_count,
        MAX(ji.updated)          AS last_updated
FROM    customfield cf
LEFT JOIN customfieldvalue cfv ON cfv.customfield = cf.id
LEFT JOIN jiraissue ji         ON ji.id = cfv.issue
WHERE   cf.customfieldtypekey NOT LIKE '%com.pyxis.greenhopper%'
  AND   cf.customfieldtypekey NOT LIKE '%com.atlassian.servicedesk%'
  AND   cf.customfieldtypekey NOT LIKE '%com.atlassian.bonfire%'
  AND   cf.customfieldtypekey NOT LIKE '%com.atlassian.jpo%'
GROUP BY cf.id, cf.cfname, cf.customfieldtypekey
ORDER BY issue_count ASC, last_updated ASC;


-- 2. Projects: issue count, lead, last activity ---------------------------------
SELECT  p.id,
        p.pkey                   AS project_key,
        p.pname                  AS project_name,
        p.lead,
        p.pcounter               AS issues_ever_created,
        COUNT(ji.id)             AS current_issue_count,
        MAX(ji.updated)          AS last_updated
FROM    project p
LEFT JOIN jiraissue ji ON ji.project = p.id
GROUP BY p.id, p.pkey, p.pname, p.lead, p.pcounter
ORDER BY last_updated ASC;


-- 3. Issue types ------------------------------------------------------------------
SELECT  it.pname                 AS issue_type,
        COUNT(ji.id)             AS issue_count,
        MAX(ji.updated)          AS last_updated
FROM    issuetype it
LEFT JOIN jiraissue ji ON ji.issuetype = it.id
GROUP BY it.pname
ORDER BY issue_count ASC;


-- 4. Workflows (by the workflow each issue is actually running) ------------------
SELECT  wf.name                  AS workflow_name,
        COUNT(ji.id)             AS issue_count,
        MAX(ji.updated)          AS last_updated
FROM    os_wfentry wf
LEFT JOIN jiraissue ji ON ji.workflow_id = wf.id
GROUP BY wf.name
ORDER BY issue_count ASC;


-- 5. Statuses ---------------------------------------------------------------------
SELECT  s.pname                  AS status_name,
        COUNT(ji.id)             AS issue_count,
        MAX(ji.updated)          AS last_updated
FROM    issuestatus s
LEFT JOIN jiraissue ji ON ji.issuestatus = s.id
GROUP BY s.pname
ORDER BY issue_count ASC;


-- 6. Saved filters: owner, JQL and who they're shared with ------------------------
--    Filters owned by deactivated users are the usual landmine during cleanup.
SELECT  f.id                     AS filter_id,
        f.filtername,
        f.authorname             AS filter_owner,
        f.reqcontent             AS filter_jql,
        sp.sharetype,
        sp.param1                AS share_param1,
        sp.param2                AS share_param2
FROM    searchrequest f
LEFT JOIN sharepermissions sp
       ON sp.entityid = f.id
      AND sp.entitytype = 'SearchRequest'
ORDER BY f.filtername;


-- 7. Filters behind agile boards ------------------------------------------------
--    Delete one of these and the board breaks.
SELECT  rv.ID                    AS board_id,
        rv.NAME                  AS board_name,
        rv.OWNER_USER_NAME       AS board_owner,
        f.id                     AS filter_id,
        f.filtername,
        f.reqcontent             AS filter_jql,
        f.authorname             AS filter_owner
FROM    AO_60DB71_RAPIDVIEW rv
LEFT JOIN searchrequest f ON f.id = rv.SAVED_FILTER_ID
ORDER BY rv.NAME;


-- 8. Filters behind dashboard gadgets -------------------------------------------
--    Gadgets store the filter as a preference value like 'filter-10200',
--    so match on the trailing id.
SELECT  sr.id                    AS filter_id,
        sr.filtername,
        sr.authorname            AS filter_owner,
        pp.id                    AS dashboard_id,
        pp.pagename              AS dashboard_name
FROM    searchrequest sr
JOIN    gadgetuserpreference gup
       ON CAST(gup.userprefvalue AS NVARCHAR(255)) LIKE '%' + CAST(sr.id AS NVARCHAR(20))
JOIN    portletconfiguration pc ON pc.id = gup.portletconfiguration
JOIN    portalpage pp           ON pp.id = pc.portalpage
ORDER BY pp.pagename, sr.filtername;
