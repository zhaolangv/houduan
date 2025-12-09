"""
检查用户统计数据是否已写入数据库
"""
import os
from dotenv import load_dotenv
from app import app, db
from models_v2 import UserSession, DailyActiveUser
from datetime import date

# 加载环境变量
load_dotenv()

def check_user_statistics():
    """检查用户统计数据"""
    with app.app_context():
        print("=" * 60)
        print("📊 用户统计数据检查")
        print("=" * 60)
        
        # 1. 检查UserSession表
        print("\n1️⃣ UserSession 表（用户会话）:")
        total_sessions = UserSession.query.count()
        print(f"   总用户数: {total_sessions}")
        
        if total_sessions > 0:
            # 显示最近的用户
            recent_sessions = UserSession.query.order_by(
                UserSession.last_active_date.desc()
            ).limit(5).all()
            
            print(f"\n   最近 {len(recent_sessions)} 个用户:")
            for session in recent_sessions:
                print(f"   - 设备ID: {session.device_id[:20]}...")
                print(f"     首次使用: {session.first_seen_date}")
                print(f"     最后活跃: {session.last_active_date}")
                print(f"     总会话数: {session.total_sessions}")
                print(f"     总题目数: {session.total_questions}")
                print()
        else:
            print("   ⚠️ 没有找到用户数据")
        
        # 2. 检查DailyActiveUser表
        print("\n2️⃣ DailyActiveUser 表（每日活跃用户）:")
        total_daily_records = DailyActiveUser.query.count()
        print(f"   总记录数: {total_daily_records}")
        
        if total_daily_records > 0:
            # 显示今日数据
            today = date.today()
            today_records = DailyActiveUser.query.filter_by(date=today).all()
            print(f"\n   今日 ({today}) 活跃用户数: {len(today_records)}")
            
            if today_records:
                print(f"\n   今日活跃用户详情:")
                for record in today_records:
                    print(f"   - 设备ID: {record.device_id[:20]}...")
                    print(f"     会话数: {record.session_count}")
                    print(f"     题目数: {record.question_count}")
                    print()
            
            # 显示最近7天的数据
            from datetime import timedelta
            seven_days_ago = today - timedelta(days=7)
            recent_records = DailyActiveUser.query.filter(
                DailyActiveUser.date >= seven_days_ago
            ).order_by(DailyActiveUser.date.desc()).all()
            
            print(f"\n   最近7天活跃记录:")
            current_date = None
            for record in recent_records:
                if record.date != current_date:
                    current_date = record.date
                    count = DailyActiveUser.query.filter_by(date=current_date).count()
                    print(f"   {current_date}: {count} 个活跃用户")
        else:
            print("   ⚠️ 没有找到每日活跃用户数据")
        
        # 3. 检查特定设备ID
        print("\n3️⃣ 检查特定设备ID:")
        test_device_id = "1de5017b1bff75dd"  # 从日志中看到的设备ID
        user_session = UserSession.query.filter_by(device_id=test_device_id).first()
        
        if user_session:
            print(f"   ✅ 找到设备ID: {test_device_id}")
            print(f"      首次使用: {user_session.first_seen_date}")
            print(f"      最后活跃: {user_session.last_active_date}")
            print(f"      总会话数: {user_session.total_sessions}")
            print(f"      总题目数: {user_session.total_questions}")
            
            # 检查今日活跃记录
            today = date.today()
            daily_record = DailyActiveUser.query.filter_by(
                device_id=test_device_id,
                date=today
            ).first()
            
            if daily_record:
                print(f"      ✅ 今日活跃记录存在")
                print(f"         会话数: {daily_record.session_count}")
                print(f"         题目数: {daily_record.question_count}")
            else:
                print(f"      ⚠️ 今日活跃记录不存在")
        else:
            print(f"   ⚠️ 未找到设备ID: {test_device_id}")
            print(f"      可能原因:")
            print(f"      1. 数据未写入数据库（检查是否有错误）")
            print(f"      2. 设备ID不匹配")
            print(f"      3. 数据库连接问题")
        
        print("\n" + "=" * 60)
        print("✅ 检查完成")
        print("=" * 60)

if __name__ == "__main__":
    try:
        check_user_statistics()
    except Exception as e:
        print(f"\n❌ 检查失败: {e}")
        import traceback
        traceback.print_exc()
