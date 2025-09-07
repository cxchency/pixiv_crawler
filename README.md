# Pixiv 用户收藏爬虫

本项目用于自动化爬取指定 Pixiv 用户的收藏作品，并下载、压缩、标记图片，支持多线程高效处理。

## 项目简介
- 自动获取目标用户的收藏夹及作品详情
- 多线程下载与压缩图片，支持插画、漫画、动图（Ugoira）
- 自动更新图片标签信息
- 支持数据库存储作品与图片信息
- 日志记录与进度条展示

## 安装方法
1. 克隆本仓库：
	```pwsh
	git clone <仓库地址>
	```
2. 安装依赖：
	```pwsh
	pip install -r requirements.txt
	```
3. 配置参数：
		 - 编辑 `config/settings.py`，填写 Pixiv 用户 ID、数据库信息、目录路径、代理等参数。
			 具体配置方法如下：
			 - TARGET_USER_ID：填写你要爬取的 Pixiv 用户的数字 ID。
			 - DATABASE_CONFIG：填写你的数据库连接信息（host、user、password、database）
			 - HEADERS：一般保持默认即可，如需自定义 UA 可修改。
			 - LOCAL_DIR/REMOTE_DIR：分别填写本地图片保存路径和远程下载路径。
			 - PROXIES：如需使用代理，填写代理地址（http/https），否则留空。
			 - 其他参数可参考 `config/settings_tmp.py` 文件中的注释说明。
	 - 配置 cookies（如需访问受限内容）：
		 1. 打开浏览器（推荐 Chrome），登录你的 Pixiv 账号。
		 2. 按 F12 打开开发者工具，切换到「网络（Network）」标签。
		 3. 刷新页面，找到任意一个请求，点击后在「请求头（Headers）」中找到 `cookie` 字段。
		4. 复制整个 cookie 字符串，粘贴到项目目录下的 `config/cookies.txt` 文件中（只能有一行，且必须为完整 cookie 字符串）。
		 5. 确保 `settings.py` 中相关配置已指向该文件，程序会自动读取。

## 使用说明
1. 启动主程序：
	```pwsh
	python main.py
	```

## 图片处理流程说明
1. 新作品图片会先下载到你设置的远程路径（REMOTE_DIR），该路径可以是本地磁盘或 SMB 网络共享路径。
2. 下载完成后，图片会自动压缩为 WebP 格式，并保存到本地路径（LOCAL_DIR）。
3. 压缩后的图片会自动写入数据库，并进行标签标记。
4. 原始图片和压缩图片路径可在配置文件中自定义。

## 功能介绍
- 获取并比对本地与远程收藏夹，自动识别新作品
- 多线程获取作品详情，提升爬取效率
- 支持插画、漫画、动图（Ugoira）三种类型的图片下载与压缩
- 自动为图片添加标签信息（ExifTool）
- 数据库操作：作品与图片信息自动 upsert
- 详细日志记录，便于排查问题