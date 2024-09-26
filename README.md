# 简易自动追剧脚本

用了一段时间 FlexGet 来追剧，觉得设置起来比较复杂，也不够灵活（也可能是不太会用），根据自己需求现学 Python 写了一个追剧脚本。

## 运行环境

Python 3.9+

需要安装第三方库：pyyaml

## 部署

脚本需要定时运行，建议放在 NAS 上，以群晖为例：

1. 将 chasing.py 和 chasing.yml 放到 NAS 上某个目录下，如：`/volume1/Work/chasing/`。
2. 在 DSM->控制面板->计划任务->新增->计划的任务->用户自定义的脚本，在任务设置里的用户自定义脚本填入
   `python /volume1/Work/chasing/chasing.py`
   ，如果安装有多个版本的 Python，建议指定完整的 Python 路径，例如：
   `/opt/bin/python /volume1/Work/chasing/chasing.py`
   ，然后设置好运行计划就可以了。

## 文件说明

-   `chasing.py`：计划任务执行脚本，其中配置日志输出的部分设置时区为`东八区`，如果是其它时区请自行修改。使用命令行参数 `test` 可以执行测试模式，只搜索资源不下载。
-   `chasing.yml`：配置文件，具体内容参见`配置文件说明`。
-   `chasing.seen`：用于保存剧集已下载的信息，该文件会自动生成，也可以手动修改，具体参见`配置文件说明`。
-   `chasing.log`：自动生成的日志文件，运行日志会保存在这里。

## 配置文件说明

配置文件主要参考范例`chasing.yml`里的注释编写，一些说明：

-   `global` 里是全局使用的配置，下载工具目前只支持 `qBittorrent` 和 `Aria2`
-   `dramas` 里是剧集的设置列表
    -   搜索资源的时候会根据 `name` 和 `keywords` 组成关键字进行搜索，如果有搜索结果，只会下载第一个。
    -   `schedules` 有两种形式，一种是按某一集的上线日期搜索，另一种是按每周几搜索，可以减少不必要的搜索，当然 `schedules` 也可以不设置，不设置的情况下则脚本每次运行都会搜索资源。
    -   `start` 是剧集上线的日期，脚本会从这个日期开始搜索资源，如果不设置，则脚本每次运行都会搜索资源。

一个简单的例子，例如要自动下载《Tulsa King》第二季 1080p 的 AMZN 版本，最简单的设置如下：

```
    - drama:
          name: Tulsa King          # 剧名
          keywords: 1080p,amzn      # 1080p，AMZN版本
          season: 2                 # 第二季
          episodes: 10              # 第二季共有10集
          download: qbittorrent     # 使用qBittorrent下载
```

这个设置将会在每次执行脚本的时候去搜索资源，直到 10 集全部下载完成。

下载过的集数信息会保存在 `chasing.seen` 文件里，默认从第 1 集开始下载，每下载成功 1 集就会更新 `chasing.seen` 文件，例如：

```
[Tulsa King]
S02 = 2
```

表示《Tulsa King》第二季已经下载了两集，下次执行将搜索第三集的资源。这个文件会自动生成，也可以手工修改，例如将 `S02 = 2` 改为 `S02 = 4`，则下次脚本执行的时候将会搜索第五集的资源。
