| year | company | training_hours | genai_tool |
| ---: | ------- | -------------: | ---------- |
| 2023 | A       |             10 | ChatGPT    |
| 2023 | A       |             12 | Copilot    |
| 2023 | B       |              8 | ChatGPT    |
| 2023 | C       |              6 | ChatGPT    |
| 2024 | A       |              9 | Copilot    |
| 2024 | B       |              7 | Gemini     |
| 2024 | B       |             11 | Copilot    |
| 2024 | C       |              5 | Copilot    |
---
For each year, return:
    number of companies (distinct)
    average training hours
    most adopted GenAI tool (the mode tool for that year)
---
CTE1: count and avg using Group by 
```
        SELECT
            year,
            COUNT(DISTINCT company) AS num_companies,
            AVG(training_hours)     AS avg_training_hours
        FROM genai
        GROUP BY year
````
| year | num_companies | avg_training_hours | 
| ---: | -     | -: | 
| 2023 | 3     |  9 |
| 2024 | 3     |  9 |

CTE2: Tool count using group by
```
        SELECT
            year,
            genai_tool,
            COUNT(*) AS tool_adoptions
        FROM genai
        GROUP BY year, genai_tool
```
| year | genai_tool | tool_adoptions |
| ---: | :--------- | -------------: |
| 2023 | ChatGPT    |              3 |
| 2023 | Copilot    |              1 |
| 2024 | Copilot    |              3 |
| 2024 | Gemini     |              1 |

CTE3: Use WINDOW function to get Rank from above CTE
```
    SELECT
        year,
        genai_tool,
        tool_adoptions,
        ROW_NUMBER() OVER (
        PARTITION BY year
        ORDER BY tool_adoptions DESC, genai_tool ASC // genai_tool in group by to break tie. If we used RANK or DENSE_RANK we would have had 2 with rn 1 in case of tie
        ) AS rn
    FROM tool_counts
```
| year | genai_tool | tool_adoptions | rn |
| ---: | :--------- | -------------: | -: |
| 2023 | ChatGPT    |              3 |  1 |
| 2023 | Copilot    |              1 |  2 |
| 2024 | Copilot    |              3 |  1 |
| 2024 | Gemini     |              1 |  2 |

FINAL
```
WITH yearly AS (
  SELECT
    year,
    COUNT(DISTINCT company) AS num_companies,
    AVG(training_hours)     AS avg_training_hours
  FROM genai
  GROUP BY year
),
tool_counts AS (
  SELECT
    year,
    genai_tool,
    COUNT(*) AS tool_adoptions // or use count(genai_tool) so null are not counted
  FROM genai
  WHERE genai_tool IS NOT NULL //if 2025 had two rows with NULL for genai_tools we dont want that counted
  GROUP BY year, genai_tool
),
top_tool AS (
  SELECT
    year,
    genai_tool AS most_adopted_tool
  FROM (
    SELECT
      year,
      genai_tool,
      tool_adoptions,
      ROW_NUMBER() OVER (
        PARTITION BY year
        ORDER BY tool_adoptions DESC, genai_tool ASC
      ) AS rn
    FROM tool_counts
  ) t
  WHERE rn = 1
)
SELECT
  y.year,
  y.num_companies,
  y.avg_training_hours,
  tt.most_adopted_tool
FROM yearly y
LEFT JOIN top_tool tt // LEFT join say for 2025 there was NULL for genai_tool
  ON y.year = tt.year
ORDER BY y.year;
```

* Null with unknown:
```
  SELECT
    year,
    COALESCE(genai_tool, 'Unknown') AS genai_tool,
    COUNT(*) AS tool_adoptions
  FROM genai
  GROUP BY year, COALESCE(genai_tool, 'Unknown')
```
--------------------------------------------
* ROWS BETWEEN N PRECEDING AND CURRENT ROW

order_id | customer_id | order_date  | price
----------|------------|--------------|---------
1        | C1          | 2024-01-01  | 100
2        | C1          | 2024-01-01  | 50
3        | C1          | 2024-01-03  | 200
4        | C2          | 2024-01-02  | 300
5        | C2          | 2024-01-04  | 100

```
SELECT
    customer_id,
    order_date,
    price,
    SUM(price) OVER (
        PARTITION BY customer_id
        ORDER BY order_date
        //ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS customer_price_till_date
FROM orders;
```
* Note here for order_id 1 and c1 and 2+c2 it is 150 because default is: `RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW`

* ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
* RANGE sees peer rows

customer_id | order_date  | price | customer_price_till_date
------------|-------------|-------|--------------------------
C1          | 2024-01-01  | 100   | 150
C1          | 2024-01-01  | 50    | 150
C1          | 2024-01-03  | 200   | 350
C2          | 2024-01-02  | 300   | 300
C2          | 2024-01-04  | 100   | 400