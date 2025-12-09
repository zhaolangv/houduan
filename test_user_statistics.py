"""
测试用户统计功能
"""
import requests
import json
import uuid

def test_user_statistics(base_url='http://localhost:5000'):
    """测试用户统计接口"""
    
    # 生成测试设备ID
    device_id = str(uuid.uuid4())
    app_version = "1.0.0"
    
    print("=" * 60)
    print("测试用户统计功能")
    print("=" * 60)
    print(f"测试设备ID: {device_id}")
    print(f"应用版本: {app_version}")
    print()
    
    # 1. 测试自动追踪（通过分析接口）
    print("1. 测试自动追踪用户活动...")
    try:
        # 模拟一个分析请求（需要实际的图片文件）
        # 这里只是演示，实际使用时需要真实的图片
        print("   ⚠️  需要实际的图片文件才能测试分析接口")
        print("   提示: 使用真实的API调用会自动追踪用户活动")
    except Exception as e:
        print(f"   ❌ 失败: {e}")
    
    print()
    
    # 2. 测试获取用户统计
    print("2. 测试获取用户统计数据...")
    try:
        response = requests.get(f"{base_url}/api/users/stats?days=30", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print("   ✅ 成功")
            if data.get('success'):
                stats = data.get('data', {})
                print(f"   - 总用户数: {stats.get('total_users', 0)}")
                print(f"   - 活跃用户数: {stats.get('active_users', 0)}")
                print(f"   - 新增用户数: {stats.get('new_users', 0)}")
                print(f"   - 平均DAU: {stats.get('avg_dau', 0)}")
            else:
                print(f"   ⚠️  返回错误: {data.get('error')}")
        else:
            print(f"   ❌ HTTP {response.status_code}: {response.text}")
    except requests.exceptions.ConnectionError:
        print("   ❌ 无法连接到服务器")
    except Exception as e:
        print(f"   ❌ 失败: {e}")
    
    print()
    
    # 3. 测试获取留存率
    print("3. 测试获取留存率...")
    try:
        response = requests.get(f"{base_url}/api/users/retention?days=7", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print("   ✅ 成功")
            if data.get('success'):
                retention = data.get('data', {})
                print(f"   - 起始日期: {retention.get('start_date')}")
                print(f"   - 新增用户数: {retention.get('new_users', 0)}")
                retention_data = retention.get('retention_data', [])
                if retention_data:
                    print(f"   - 留存数据: {len(retention_data)}条")
                    # 显示第1天和第7天的留存率
                    for item in retention_data:
                        if item.get('day') in [0, 1, 7]:
                            print(f"     Day {item.get('day')}: {item.get('retention_rate', 0)}%")
            else:
                print(f"   ⚠️  返回错误: {data.get('error')}")
        else:
            print(f"   ❌ HTTP {response.status_code}: {response.text}")
    except requests.exceptions.ConnectionError:
        print("   ❌ 无法连接到服务器")
    except Exception as e:
        print(f"   ❌ 失败: {e}")
    
    print()
    
    # 4. 测试获取Cohort留存率
    print("4. 测试获取Cohort留存率...")
    try:
        response = requests.get(f"{base_url}/api/users/cohort?cohort_days=7&retention_days=30", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print("   ✅ 成功")
            if data.get('success'):
                cohort = data.get('data', {})
                cohorts = cohort.get('cohorts', [])
                print(f"   - Cohort数量: {len(cohorts)}")
                for c in cohorts[:3]:  # 只显示前3个
                    print(f"     {c.get('cohort_date')}: 新增{c.get('new_users', 0)}用户")
            else:
                print(f"   ⚠️  返回错误: {data.get('error')}")
        else:
            print(f"   ❌ HTTP {response.status_code}: {response.text}")
    except requests.exceptions.ConnectionError:
        print("   ❌ 无法连接到服务器")
    except Exception as e:
        print(f"   ❌ 失败: {e}")
    
    print()
    print("=" * 60)
    print("测试完成！")
    print("=" * 60)
    print()
    print("提示:")
    print("1. 用户活动会在调用 /api/questions/analyze 时自动追踪")
    print("2. 需要在请求头或参数中提供 device_id")
    print("3. 查看详细文档: 用户留存率统计说明.md")


if __name__ == '__main__':
    import sys
    
    base_url = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:5000'
    test_user_statistics(base_url)
