import requests
import os
import re
from datetime import datetime, timedelta

# ================= 配置区域 =================
# 目标URL
URL_SEARCH = "https://course.jzmu.edu.cn/Api/Resource/SearchCategoryResource"
URL_PLAY_INFO = "https://course.jzmu.edu.cn/Api/Resource/GetPlayInfoByFileUniqueID"

def get_user_date_input(prompt_text):
    """
    获取用户输入的北京时间日期，并转换为UTC的ISO 8601格式（固定零点）
    """
    while True:
        user_input = input(prompt_text).strip()
        # 如果用户直接回车，表示不限制该时间
        if not user_input:
            return ""
        
        try:
            # 1. 解析用户输入的北京时间日期 (格式: YYYY-MM-DD)
            beijing_date = datetime.strptime(user_input, "%Y-%m-%d")
            
            # 2. 北京时间减去8小时，转换为UTC零时区时间
            utc_time = beijing_date - timedelta(hours=8)
            
            # 3. 格式化为接口要求的格式：2026-08-04T16:00:00.000Z
            iso_utc_str = utc_time.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            print(f"  [转换成功] 北京时间日期: {user_input} -> UTC格式: {iso_utc_str}")
            return iso_utc_str
            
        except ValueError:
            print("  [格式错误] 请输入正确的日期格式，例如: 2026-08-04")

# 获取用户输入的日期
start_time_str = get_user_date_input("请输入开始日期 (格式: YYYY-MM-DD, 直接回车跳过): ")
end_time_str = get_user_date_input("请输入结束日期 (格式: YYYY-MM-DD, 直接回车跳过): ")

# POST请求的负载数据
PAYLOAD = {
    "SectionID": -1,
    "ResourceType": -1,
    "CategoryID": 237,
    "ExcludeChild": False,
    "StartSize": 0,
    "EndSize": 0,
    "StartTime": start_time_str,
    "EndTime": end_time_str,
    "PageCondition": {
        "Order": False,
        "OrderField": "PublishTime",
        "PageSize": 999,
        "PageCount": 0,
        "TotalCount": 0,
        "PageIndex": 1
    }
}

# 请求头（模拟浏览器，防止被拦截）
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
    "Content-Type": "application/json"
}

# 下载保存的目录（会自动创建）
SAVE_DIR = "downloaded_files"

# ================= 脚本逻辑 =================

def sanitize_filename(name):
    """
    清洗文件名，移除操作系统不允许的字符 (如 \ / : * ? " < > |)
    """
    return re.sub(r'[\\/*?:"<>|]', "_", name)

def get_extension_from_stream(url):
    """
    从HttpStream链接末尾提取扩展名
    例如：...$doc -> .doc
    """
    if '$' in url:
        # 获取最后一个$后面的内容
        ext = url.split('$')[-1]
        # 简单的安全检查，确保是字母且长度合理
        if ext.isalnum() and len(ext) <= 5:
            return f".{ext}"
    return ""

def main():
    session = requests.Session()
    
    # 创建保存目录
    if not os.path.exists(SAVE_DIR):
        os.makedirs(SAVE_DIR)

    print("正在获取资源列表...")
    try:
        # 1. 发送POST请求获取列表
        response = session.post(URL_SEARCH, json=PAYLOAD, headers=HEADERS, timeout=10)
        response.raise_for_status()
        json_data = response.json()
    except Exception as e:
        print(f"获取列表失败: {e}")
        return

    if json_data.get("ret") != 1:
        print(f"接口返回错误: {json_data.get('msg')}")
        return

    data_list = json_data.get("data", [])
    print(f"共找到 {len(data_list)} 个资源，开始处理...\n")

    # 统计变量
    success_count = 0
    fail_count = 0
    total_count = len(data_list)
    
    # 遍历资源
    for item in data_list:
        resource_name = item.get("ResourceName")
        unique_id = item.get("UniqueID")
        
        if not resource_name or not unique_id:
            print(f"跳过无效数据: {item}")
            continue

        print(f"正在处理: [{resource_name}]")
        
        try:
            # 2. 获取播放/下载信息
            play_info_url = f"{URL_PLAY_INFO}?uniqueid={unique_id}"
            res_play = session.get(play_info_url, headers=HEADERS, timeout=10)
            play_json = res_play.json()
            
            if play_json.get("ret") != 1:
                print(f"  获取下载链接失败: {play_json.get('msg')}")
                fail_count += 1
                continue
            
            http_stream = play_json["data"].get("HttpStream")
            if not http_stream:
                print("  未找到HttpStream链接")
                fail_count += 1
                continue
            
            # 3. 准备下载
            # 清洗文件名
            safe_name = sanitize_filename(resource_name)
            # 提取扩展名 (如 .doc, .pdf)
            ext = get_extension_from_stream(http_stream)
            # 完整路径
            file_path = os.path.join(SAVE_DIR, safe_name + ext)
            
            # 4. 执行下载
            print(f"  下载链接: {http_stream}")
            with session.get(http_stream, stream=True, timeout=20) as r:
                r.raise_for_status()
                with open(file_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            
            print(f"  下载成功: {file_path}\n")
            success_count += 1
            
        except Exception as e:
            print(f"  下载出错: {e}\n")
            fail_count += 1

    # ================= 输出统计 =================
    print("="*30)
    print("下载任务完成")
    print(f"总资源数 (ResourceName/UniqueID): {total_count}")
    print(f"下载成功次数: {success_count}")
    print(f"下载失败次数: {fail_count}")
    print("="*30)

if __name__ == "__main__":
    main()
