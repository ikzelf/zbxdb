# SAP-HANA-SQL-Statements

SAP Hana SQL Statements for retrieving performance and status information.

To find row  store utilization:

```
SELECT round (sum(USED_FIXED_PART_SIZE + USED_VARIABLE_PART_SIZE)/1024/1024) AS "Row Tables MB" 
FROM M_RS_TABLES;
```

To find column store utilization :- Completado

```
SELECT round (sum(MEMORY_SIZE_IN_TOTAL)/1024/1024) AS "Column Tables MB"  
FROM M_CS_TABLES;
```

To find log segments and services related with its state

```
SELECT b.host, b.service_name, a.state, COUNT(*) 
FROM "PUBLIC"."M_LOG_SEGMENTS" a 
JOIN "PUBLIC"."M_SERVICES" b on (a.host = b.host AND a.port = b.port) 
GROUP BY b.host, b.service_name, a.state;
```

To find Hana DB Size

```
SELECT ROUND (sum(allocated_page_size)/1024/1024/1024) "Value GB" 
FROM m_converter_statistics;
```

To check the peak memory usage

```
SELECT TOP 1 HOST, SERVER_TIMESTAMP, round(TOTAL_MEMORY_USED_SIZE/1024/1024/1024, 2) as "Used Memory GB" 
FROM _SYS_STATISTICS.HOST_SERVICE_MEMORY 
WHERE SERVICE_NAME = 'indexserver'
ORDER BY TOTAL_MEMORY_USED_SIZE DESC;
```

To list out the top 100 memory usage in HANA database between a specified date and time ;

```
SELECT TOP 100 ROUND(TOTAL_MEMORY_USED_SIZE/1024/1024/1024, 2) AS "Used Memory GB", HOST, SERVER_TIMESTAMP 
FROM _SYS_STATISTICS.HOST_SERVICE_MEMORY 
WHERE SERVER_TIMESTAMP 
BETWEEN '01.04.2018 08:00:00' AND '02.12.2021 18:00:00'
ORDER BY TOTAL_MEMORY_USED_SIZE DESC;
```

To list all IDLE sessions:

```
SELECT CONNECTION_ID, IDLE_TIME 
FROM M_CONNECTIONS 
WHERE CONNECTION_STATUS = 'IDLE' AND CONNECTION_TYPE = 'Remote' 
ORDER BY IDLE_TIME DESC;
```

Product usage:
```
SELECT product_usage 
FROM m_license;
```

Table in memory value:
```
SELECT (sum(memory_size_in_total)/1024/1024/1024) AS "VALUE IN MB"
FROM M_CS_TABLES;
```

Total successful complete data backup

```
SELECT COUNT(backup_id) 
FROM M_BACKUP_CATALOG 
WHERE entry_type_name = 'complete data backup'  and state_name = 'successful';
```

Disk Size:
```
SELECT ROUND(SUM((disk_size)/1024/1024/1024)) 
FROM m_table_persistence_statistics;
```

