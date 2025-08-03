# 1.设备异常检测，上报告警信息场景

## 1.创建图空间

```
CREATE SPACE DeviceManagement (partition_num=10, replica_factor=1, vid_type=INT64);
USE DeviceManagement;
```



## 2.创建Tag和Edge



### 2.1 Tag：设备、传感器和报警

```
CREATE TAG Device (
    device_id INT64,         -- 设备ID
    device_name STRING,      -- 设备名称
    device_type STRING,      -- 设备类型（例如：温度传感器、压力传感器等）
    status STRING           -- 设备状态（例如：正常、故障）
);

CREATE TAG Sensor (
    sensor_id INT64,         -- 传感器ID
    sensor_type STRING,      -- 传感器类型（例如：温度、压力、湿度等）
    value FLOAT              -- 传感器的值（例如：温度、湿度等）
);

CREATE TAG Alarm (
    alarm_id INT64,           -- 报警ID
    alarm_type STRING,        -- 报警类型（例如：温度过高、压力过大等）
    alarm_level STRING,       -- 报警级别（例如：低、中、高）
    message STRING            -- 报警信息
);
```



### 2.2 Edge：设备与传感器、报警之间的关系

```
CREATE EDGE ConnectedTo (    -- 设备与传感器的关系
    start_time DATETIME,    -- 连接开始时间
    end_time DATETIME       -- 连接结束时间
);

CREATE EDGE TriggeredBy (   -- 传感器与报警的关系
    trigger_time DATETIME  -- 触发报警的时间
);
```



## 3.测试数据

```
-- 插入设备数据
INSERT VERTEX Device (device_id, device_name, device_type, status) VALUES
    1:(1, "温度传感器A", "温度传感器", "正常"),
    2:(2, "温度传感器B", "温度传感器", "故障"),
    3:(3, "压力传感器A", "压力传感器", "正常");

-- 插入传感器数据
INSERT VERTEX Sensor (sensor_id, sensor_type, value) VALUES
    101:(101, "温度", 25.5),
    102:(102, "温度", 75.2),
    103:(103, "压力", 5.8);

-- 插入报警数据
INSERT VERTEX Alarm (alarm_id, alarm_type, alarm_level, message) VALUES
    1001:(1001, "温度过高", "高", "温度传感器B温度超出正常范围!"),
    1002:(1002, "压力过大", "中", "压力传感器A压力超出正常范围!");

-- 插入设备与传感器之间的关系
INSERT EDGE ConnectedTo(start_time, end_time) VALUES
  1->101: (datetime("2025-07-01 10:00:00"), datetime("2025-07-01 12:00:00")),
  2->102: (datetime("2025-07-01 11:00:00"), datetime("2025-07-01 13:00:00")),
  3->103: (datetime("2025-07-01 12:00:00"), datetime("2025-07-01 14:00:00"));

-- 插入传感器与报警之间的关系
INSERT EDGE TriggeredBy (trigger_time) VALUES
    101->1001:(datetime("2025-07-01 11:00:00")),
    102->1001:(datetime("2025-07-01 12:00:00")),
    103->1002:(datetime("2025-07-01 12:30:00"));
```



## 4.查询数据



### 4.1 查询点数据

```
-- 查询tag类型为Alarm的点数据
MATCH (d:Alarm) RETURN d;

MATCH (d:Alarm)
RETURN properties(d).alarm_id, 
       properties(d).alarm_level, 
       properties(d).message;

-- 条件语句查询
MATCH (d:Alarm)
WHERE properties(d).alarm_level == "高" 
RETURN properties(d).alarm_id, 
       properties(d).alarm_level, 
       properties(d).message;       

-- 查询tag类型为Alarm，vid等于1001 的点数据
FETCH PROP ON Alarm 1001 YIELD properties(vertex);

FETCH PROP ON Alarm 1001 YIELD properties(vertex).alarm_level;
```



### 4.2 查询边数据

```
-- 查询图中所有 ConnectedTo 类型的边，返回边属性以及起点/终点的 ID。
MATCH (a)-[e:ConnectedTo]->(b) RETURN e.start_time, e.end_time, id(a), id(b);

FETCH PROP ON ConnectedTo 1 -> 101 YIELD edge AS e;
```



### 4.3复杂查询

```
-- 查询设备状态与关联的报警信息  查询故障设备的相关报警信息
MATCH (d:Device)-[:ConnectedTo]->(s:Sensor)-[:TriggeredBy]->(a:Alarm)
WHERE properties(d).status == "故障"  
RETURN properties(d).device_name AS `设备名称`, properties(s).sensor_type AS `传感器类型`, properties(a).alarm_type AS `报警类型`, properties(a).message AS `报警信息`;

-- 查询传感器值超过阈值的设备  设置阈值为70
MATCH (d:Device)-[:ConnectedTo]->(s:Sensor)
WHERE properties(s).value > 70  
RETURN properties(d).device_name AS `设备名称`, properties(s).sensor_type AS `传感器类型`, properties(s).value AS `传感器值`;

-- 查询特定报警级别的设备 查询高等级报警的设备
MATCH (d:Device)-[:ConnectedTo]->(s:Sensor)-[:TriggeredBy]->(a:Alarm)
WHERE properties(a).alarm_level == "高"  
RETURN properties(d).device_name AS `设备名称`, properties(a).alarm_type AS `报警类型`, properties(a).message AS `报警信息`;

-- 查询设备及其传感器的工作时间
MATCH (d:Device)-[rel:ConnectedTo]->(s:Sensor)
RETURN 
  properties(d).device_name AS `设备名称`, 
  properties(s).sensor_type AS `传感器类型`, 
  min(properties(rel).start_time) AS `开始时间`, 
  max(properties(rel).end_time) AS `结束时间`;
  
-- 查询某个时间之后的报警信息  
MATCH (d:Device)-[:ConnectedTo]->(s:Sensor)-[t:TriggeredBy]->(a:Alarm)
WHERE properties(t).trigger_time > datetime("2025-07-01 12:00:00")
RETURN properties(d).device_name AS `设备名称`, properties(a).alarm_type AS `报警类型`, properties(t).trigger_time AS `触发时间`, properties(a).message AS `报警信息`;  
```

# 2.博客平台场景

## 🌐 场景背景说明

我们模拟一个博客平台，包含以下实体和关系：

### 实体（Tag）：

- 用户 (`user`)
- 博客文章 (`post`)
- 标签 (`tag`)

### 关系（Edge）：

- `follow`：用户关注用户
- `like`：用户点赞博客
- `comment`：用户评论博客
- `publish`：用户发布博客
- `tagged`：博客打上标签

## 1.创建图空间

```
CREATE SPACE IF NOT EXISTS blog_graph(partition_num=10, replica_factor=1, vid_type=fixed_string(32));
USE blog_graph;
```

## 2. 创建 Tag（顶点）和Edge（边）

```
CREATE TAG IF NOT EXISTS user(name string, gender string, age int, email string);
CREATE TAG IF NOT EXISTS post(title string, content string, publish_time timestamp);
CREATE TAG IF NOT EXISTS `tag`(name string);

CREATE EDGE IF NOT EXISTS follow(degree int);         -- degree表示关注强度
CREATE EDGE IF NOT EXISTS like(strength double);      -- strength表示喜欢程度
CREATE EDGE IF NOT EXISTS comment(content string, `time` timestamp);
CREATE EDGE IF NOT EXISTS publish(`time` timestamp);
CREATE EDGE IF NOT EXISTS tagged(weight double);
```

## 3.测试输入

```
-- 插入用户（user）
INSERT VERTEX user(name, gender, age, email) VALUES \
  "u1":("张三", "男", 28, "zhangsan@example.com"), \
  "u2":("李四", "女", 25, "lisi@example.com"), \
  "u3":("王五", "男", 30, "wangwu@example.com"), \
  "u4":("赵六", "女", 22, "zhaoliu@example.com");
  
-- 插入博客文章（post）
INSERT VERTEX post(title, content, publish_time) VALUES \
  "p1":("Nebula Graph入门", "本文介绍如何使用Nebula Graph进行数据建模。", now()), \
  "p2":("图数据库的优势", "对比传统数据库，图数据库在关系查询上具有巨大优势。", now()), \
  "p3":("如何设计博客系统", "一个博客系统的设计与实现思路。", now()), \
  "p4":("AI与图数据库", "AI在图数据库中的应用前景。", now());
  
-- 插入标签（tag）
INSERT VERTEX `tag`(name) VALUES \
  "t1":("图数据库"), \
  "t2":("Nebula Graph"), \
  "t3":("AI"), \
  "t4":("数据库设计");
  
-- 用户关注
INSERT EDGE follow(degree) VALUES \
  "u1" -> "u2":(5), \
  "u1" -> "u3":(3), \
  "u2" -> "u4":(4), \
  "u3" -> "u4":(2);

-- 用户点赞博客
INSERT EDGE like(strength) VALUES \
  "u1" -> "p1":(0.8), \
  "u2" -> "p1":(0.9), \
  "u3" -> "p2":(0.7), \
  "u4" -> "p3":(0.6);

-- 用户评论博客
INSERT EDGE comment(content, `time`) VALUES \
  "u1" -> "p2":("写得不错！", now()), \
  "u2" -> "p1":("例子很清晰", now()), \
  "u3" -> "p3":("设计思路很实用", now()), \
  "u4" -> "p4":("未来感十足", now());

-- 用户发布博客
INSERT EDGE publish(`time`) VALUES \
  "u1" -> "p1":(now()), \
  "u2" -> "p2":(now()), \
  "u3" -> "p3":(now()), \
  "u4" -> "p4":(now());

-- 博客添加标签
INSERT EDGE tagged(weight) VALUES \
  "p1" -> "t1":(0.9), \
  "p1" -> "t2":(1.0), \
  "p2" -> "t1":(0.7), \
  "p3" -> "t4":(0.8), \
  "p4" -> "t1":(0.6), \
  "p4" -> "t3":(0.9);
```

## 4.查询数据

### 4.1 查询某个用户发布的所有博客

```
-- 查询某个用户发布的所有博客
GO FROM "u1" OVER publish YIELD dst(edge) AS post_id \
| FETCH PROP ON post $-.post_id YIELD properties(vertex).title AS title;
```

### 4.2 查询某个用户的所有粉丝（即谁关注了他） 

```
-- 查询某个用户的所有粉丝（即谁关注了他）
GO FROM "u2" OVER follow REVERSELY YIELD src(edge) AS follower_id \
| FETCH PROP ON user $-.follower_id YIELD properties(vertex).name AS name;
```

### 4.3 查询某篇博客的所有评论及评论者

```
-- 查询某篇博客的所有评论及评论者
GO FROM "p1" OVER comment REVERSELY YIELD src(edge) AS user_id, properties(edge).content AS comment_content \
| FETCH PROP ON user $-.user_id YIELD properties(vertex).name AS user_name, $-.comment_content AS comment;
```

### 4.4 查询某篇博客的点赞用户及点赞强度

```
-- 查询某篇博客的点赞用户及点赞强度
GO FROM "p1" OVER like REVERSELY YIELD src(edge) AS user_id, properties(edge).strength AS like_strength \
| FETCH PROP ON user $-.user_id YIELD properties(vertex).name AS user_name, $-.like_strength AS strength;

# 分步骤实现
# 第一步：获取评论该博客的用户ID和评论内容
$comments = GO FROM "p1" OVER comment REVERSELY 
YIELD src(edge) AS user_id, properties(edge).content AS comment_content;

# 第二步：根据用户ID获取用户姓名
$user_info = FETCH PROP ON user $comments.user_id 
YIELD properties(vertex).name AS user_name, vertex AS user_id;

# 第三步：合并用户信息和评论内容
YIELD $comments.comment_content AS comment, $user_info.user_name AS user_name;
```

### 4.5 查询某篇博客的标签

```
-- 查询某篇博客的标签
GO FROM "p1" OVER tagged YIELD dst(edge) AS tag_id \
| FETCH PROP ON `tag` $-.tag_id YIELD properties(vertex).name AS tag_name;
```

### 4.6 查找与某个用户有共同点赞的用户（用于推荐）

```
-- 查找与某个用户有共同点赞的用户（用于推荐）
# 查找用户u1点赞的所有博客
$u1_likes = GO FROM "u1" OVER like YIELD dst(edge) AS post_id;

# 查找其他用户点赞这些博客的记录
GO FROM $u1_likes.post_id OVER like REVERSELY \
WHERE src(edge) != "u1" \
YIELD src(edge) AS other_user_id, count(*) AS common_likes \
ORDER BY common_likes DESC \
LIMIT 3;
```

### 4.7 查找某个用户发布的博客中，哪些标签出现频率最高（用于兴趣分析）

```
-- 查找某个用户发布的博客中，哪些标签出现频率最高（用于兴趣分析）
# 查找用户u1发布的博客
$u1_posts = GO FROM "u1" OVER publish YIELD dst(edge) AS post_id;

# 查找这些博客的标签
GO FROM $u1_posts.post_id OVER tagged \
YIELD dst(edge) AS tag_id \
| GROUP BY $-.tag_id YIELD $-.tag_id, count(*) AS freq \
| FETCH PROP ON tag $-.tag_id YIELD properties(vertex).name AS tag_name, $-.freq AS frequency \
ORDER BY frequency DESC;
```

### 4.8 查找用户的朋友的朋友（社交网络扩散）

```
-- 查找用户的朋友的朋友（社交网络扩散）
# 查找用户u1的所有好友
$friends = GO FROM "u1" OVER follow YIELD dst(edge) AS friend_id;

# 查找这些好友的好友
GO FROM $friends.friend_id OVER follow YIELD dst(edge) AS friend_of_friend_id \
| WHERE friend_of_friend_id != "u1" \
| GROUP BY $-.friend_of_friend_id YIELD $-.friend_of_friend_id, count(*) AS mutual_friends \
ORDER BY mutual_friends DESC;
```



## 5.数据模型图

### 一、顶点（Vertex / Tag）

| Tag 名称 | 属性（Properties）                 |
| -------- | ---------------------------------- |
| `user`   | `name`, `gender`, `age`, `email`   |
| `post`   | `title`, `content`, `publish_time` |
| `tag`    | `name`                             |

### 二、边（Edge / Edge Type）

| 边类型名  | 起点            | 终点                                | 属性（Properties） |
| --------- | --------------- | ----------------------------------- | ------------------ |
| `follow`  | `user` → `user` | `degree`（表示关注强度）            |                    |
| `like`    | `user` → `post` | `strength`（表示喜欢程度）          |                    |
| `comment` | `user` → `post` | `content`, `time`（评论内容和时间） |                    |
| `publish` | `user` → `post` | `time`（发布时间）                  |                    |
| `tagged`  | `post` → `tag`  | `weight`（标签权重）                |                    |

### 图结构（可视化文本版）

```
[user]──(follow)──→[user]
   │
   └──(like)────→[post]←──(tagged)──[tag]
   │               ↑
   │               └──(comment)
   │               └──(publish)
```

### 更详细的结构说明：

- **用户（user）**：

  - 可以关注其他用户（`follow`）
  - 可以点赞、评论、发布博客（`like`, `comment`, `publish`）

- **博客（post）**：

  - 可以被打上多个标签（`tagged`）
  - 可以被多个用户点赞、评论

- **标签（tag）**：

  - 与博客建立关联，表示该博客属于哪些主题

### ✅ 示例数据关系图（以 u1 为例）

  ```
  [u1: 张三]
     │
     ├── follow → [u2: 李四]
     ├── follow → [u3: 王五]
     ├── like → [p1: Nebula Graph入门] (strength=0.8)
     ├── comment → [p2: 图数据库的优势] (content="写得不错！")
     └── publish → [p1: Nebula Graph入门] (time=now)
  
  [p1: Nebula Graph入门]
     └── tagged → [t1: 图数据库] (weight=0.9)
     └── tagged → [t2: Nebula Graph] (weight=1.0)
  ```

  

  

# 3.公共语法



## 1.查询nebula数据库版本

```
SHOW VERSION;
```

