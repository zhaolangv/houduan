"""
公考复盘工具 - GUI界面
支持拖拽图片到窗口，自动调用API解析
"""
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
from tkinterdnd2 import DND_FILES, TkinterDnD
import requests
import json
import os
from PIL import Image, ImageTk
import io
import threading

class GongkaoApp:
    def __init__(self, root):
        self.root = root
        self.root.title("公考复盘工具 - AI解析")
        self.root.geometry("900x700")
        self.root.configure(bg='#f0f0f0')
        
        # API地址
        self.api_url = "http://localhost:5000/api/analyze"
        
        # 当前图片路径
        self.current_image_path = None
        self.current_image = None
        
        self.setup_ui()
        
    def setup_ui(self):
        """设置UI界面"""
        # 标题
        title_frame = tk.Frame(self.root, bg='#2c3e50', height=60)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)
        
        title_label = tk.Label(
            title_frame,
            text="公考复盘工具 - AI题目解析",
            font=("Microsoft YaHei", 16, "bold"),
            bg='#2c3e50',
            fg='white'
        )
        title_label.pack(pady=15)
        
        # 主容器
        main_frame = tk.Frame(self.root, bg='#f0f0f0')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 左侧：图片区域
        left_frame = tk.Frame(main_frame, bg='white', relief=tk.RAISED, bd=2)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # 拖拽区域
        drop_label = tk.Label(
            left_frame,
            text="📁 拖拽图片到这里\n\n或点击选择图片",
            font=("Microsoft YaHei", 12),
            bg='white',
            fg='#7f8c8d',
            cursor="hand2"
        )
        drop_label.pack(pady=50)
        drop_label.bind("<Button-1>", self.select_image)
        
        # 图片预览区域
        self.image_label = tk.Label(
            left_frame,
            text="",
            bg='white'
        )
        self.image_label.pack(pady=10, padx=10)
        
        # 启用拖拽
        self.image_label.drop_target_register(DND_FILES)
        self.image_label.dnd_bind('<<Drop>>', self.on_drop)
        drop_label.drop_target_register(DND_FILES)
        drop_label.dnd_bind('<<Drop>>', self.on_drop)
        
        # 图片信息
        self.image_info_label = tk.Label(
            left_frame,
            text="",
            font=("Microsoft YaHei", 9),
            bg='white',
            fg='#95a5a6'
        )
        self.image_info_label.pack(pady=5)
        
        # 解析按钮
        self.analyze_button = tk.Button(
            left_frame,
            text="🚀 开始解析",
            font=("Microsoft YaHei", 12, "bold"),
            bg='#3498db',
            fg='white',
            relief=tk.FLAT,
            padx=20,
            pady=10,
            cursor="hand2",
            command=self.analyze_question,
            state=tk.DISABLED
        )
        self.analyze_button.pack(pady=20)
        
        # 右侧：结果显示区域
        right_frame = tk.Frame(main_frame, bg='white', relief=tk.RAISED, bd=2)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        # 结果标题
        result_title = tk.Label(
            right_frame,
            text="📝 解析结果",
            font=("Microsoft YaHei", 14, "bold"),
            bg='white',
            fg='#2c3e50'
        )
        result_title.pack(pady=10)
        
        # 题目类型选择
        type_frame = tk.Frame(right_frame, bg='white')
        type_frame.pack(pady=10, padx=10, fill=tk.X)
        
        tk.Label(
            type_frame,
            text="题目类型:",
            font=("Microsoft YaHei", 10),
            bg='white'
        ).pack(side=tk.LEFT, padx=5)
        
        self.question_type = ttk.Combobox(
            type_frame,
            values=["图推", "言语理解", "判断推理", "数量关系", "资料分析", "常识判断"],
            state="readonly",
            width=15
        )
        self.question_type.set("图推")
        self.question_type.pack(side=tk.LEFT, padx=5)
        
        # 题目ID输入
        id_frame = tk.Frame(right_frame, bg='white')
        id_frame.pack(pady=5, padx=10, fill=tk.X)
        
        tk.Label(
            id_frame,
            text="题目ID:",
            font=("Microsoft YaHei", 10),
            bg='white'
        ).pack(side=tk.LEFT, padx=5)
        
        self.question_id_entry = tk.Entry(id_frame, width=20)
        self.question_id_entry.pack(side=tk.LEFT, padx=5)
        
        # 状态标签
        self.status_label = tk.Label(
            right_frame,
            text="等待图片...",
            font=("Microsoft YaHei", 9),
            bg='white',
            fg='#95a5a6'
        )
        self.status_label.pack(pady=5)
        
        # 结果显示区域
        self.result_text = scrolledtext.ScrolledText(
            right_frame,
            wrap=tk.WORD,
            font=("Microsoft YaHei", 10),
            bg='#f8f9fa',
            fg='#2c3e50',
            relief=tk.FLAT,
            padx=10,
            pady=10
        )
        self.result_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 底部状态栏
        self.status_bar = tk.Label(
            self.root,
            text="就绪 | API: http://localhost:5000",
            font=("Microsoft YaHei", 8),
            bg='#34495e',
            fg='white',
            anchor=tk.W,
            padx=10
        )
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
    def select_image(self, event=None):
        """选择图片文件"""
        file_path = filedialog.askopenfilename(
            title="选择图片",
            filetypes=[
                ("图片文件", "*.jpg *.jpeg *.png *.gif *.bmp"),
                ("所有文件", "*.*")
            ]
        )
        if file_path:
            self.load_image(file_path)
    
    def on_drop(self, event):
        """处理拖拽文件"""
        files = self.root.tk.splitlist(event.data)
        if files:
            file_path = files[0]
            # 检查是否是图片文件
            if file_path.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp')):
                self.load_image(file_path)
            else:
                messagebox.showwarning("警告", "请拖拽图片文件！")
    
    def load_image(self, file_path):
        """加载并显示图片"""
        try:
            self.current_image_path = file_path
            
            # 加载图片
            img = Image.open(file_path)
            
            # 调整大小以适应显示区域
            max_width = 400
            max_height = 300
            img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
            
            # 转换为Tkinter格式
            self.current_image = ImageTk.PhotoImage(img)
            self.image_label.config(image=self.current_image, text="")
            
            # 显示图片信息
            file_name = os.path.basename(file_path)
            file_size = os.path.getsize(file_path) / 1024  # KB
            info_text = f"📷 {file_name}\n大小: {file_size:.1f} KB"
            self.image_info_label.config(text=info_text)
            
            # 启用解析按钮
            self.analyze_button.config(state=tk.NORMAL)
            self.status_label.config(text="图片已加载，可以开始解析", fg='#27ae60')
            
        except Exception as e:
            messagebox.showerror("错误", f"加载图片失败：{str(e)}")
    
    def analyze_question(self):
        """解析题目"""
        if not self.current_image_path:
            messagebox.showwarning("警告", "请先选择或拖拽图片！")
            return
        
        # 禁用按钮
        self.analyze_button.config(state=tk.DISABLED)
        self.status_label.config(text="正在解析中...", fg='#3498db')
        self.result_text.delete(1.0, tk.END)
        self.result_text.insert(tk.END, "正在解析，请稍候...\n\n")
        
        # 在新线程中执行API调用
        thread = threading.Thread(target=self._call_api)
        thread.daemon = True
        thread.start()
    
    def _call_api(self):
        """调用API（在后台线程中执行）"""
        try:
            # 准备请求数据
            question_type = self.question_type.get()
            question_id = self.question_id_entry.get().strip() or None
            
            # 先上传图片文件
            upload_url = "http://localhost:5000/api/upload"
            try:
                with open(self.current_image_path, 'rb') as f:
                    files = {'file': (os.path.basename(self.current_image_path), f, 'image/jpeg')}
                    upload_response = requests.post(upload_url, files=files, timeout=30)
                    
                    if upload_response.status_code != 200:
                        error_msg = f"上传失败 (状态码: {upload_response.status_code})"
                        try:
                            error_data = upload_response.json()
                            error_msg = error_data.get('error', error_msg)
                        except:
                            error_msg = upload_response.text[:200] if upload_response.text else error_msg
                        self.root.after(0, self._show_error, f"上传图片失败：{error_msg}")
                        return
                    
                    upload_result = upload_response.json()
            except requests.exceptions.ConnectionError:
                self.root.after(0, self._show_error, "无法连接到API服务器！\n\n请确保服务已启动：\npython app.py")
                return
            except requests.exceptions.Timeout:
                self.root.after(0, self._show_error, "上传图片超时，请稍后重试")
                return
            except Exception as e:
                self.root.after(0, self._show_error, f"上传图片出错：{str(e)}")
                return
            
            if not upload_result.get('success'):
                error_msg = upload_result.get('error', '未知错误')
                self.root.after(0, self._show_error, f"上传图片失败：{error_msg}")
                return
            
            # 获取上传后的图片URL
            image_url = upload_result['data']['image_url']
            
            # 调用解析API
            data = {
                "question_type": question_type,
                "image_url": image_url
            }
            
            if question_id:
                data["question_id"] = question_id
            
            # 调用API
            try:
                response = requests.post(self.api_url, json=data, timeout=60)
                
                if response.status_code != 200:
                    error_msg = f"解析失败 (状态码: {response.status_code})"
                    try:
                        error_data = response.json()
                        error_msg = error_data.get('error', error_msg)
                    except:
                        error_msg = response.text[:200] if response.text else error_msg
                    self.root.after(0, self._show_error, error_msg)
                    return
                
                result = response.json()
            except requests.exceptions.ConnectionError:
                self.root.after(0, self._show_error, "无法连接到API服务器！\n\n请确保服务已启动：\npython app.py")
                return
            except requests.exceptions.Timeout:
                self.root.after(0, self._show_error, "解析请求超时，请稍后重试\n\n（首次解析可能需要较长时间）")
                return
            except Exception as e:
                self.root.after(0, self._show_error, f"调用API出错：{str(e)}")
                return
            
            # 在主线程中更新UI
            self.root.after(0, self._update_result, result)
            
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            # 只显示关键错误信息，不显示完整traceback
            error_msg = str(e)
            if len(error_msg) > 200:
                error_msg = error_msg[:200] + "..."
            self.root.after(0, self._show_error, f"解析失败：{error_msg}")
    
    def _update_result(self, result):
        """更新结果显示"""
        self.analyze_button.config(state=tk.NORMAL)
        
        if result.get('success'):
            data = result.get('data', {})
            analysis = data.get('analysis', '')
            from_cache = data.get('from_cache', False)
            question_id = data.get('question_id', '')
            
            # 显示结果
            self.result_text.delete(1.0, tk.END)
            
            # 添加标题
            self.result_text.insert(tk.END, "=" * 50 + "\n")
            self.result_text.insert(tk.END, "AI解析结果\n")
            self.result_text.insert(tk.END, "=" * 50 + "\n\n")
            
            # 缓存状态
            cache_status = "✅ 使用缓存（节省费用）" if from_cache else "🆕 首次解析（已缓存）"
            self.result_text.insert(tk.END, f"状态: {cache_status}\n")
            if question_id:
                self.result_text.insert(tk.END, f"题目ID: {question_id}\n")
            self.result_text.insert(tk.END, "\n" + "-" * 50 + "\n\n")
            
            # 解析内容
            self.result_text.insert(tk.END, analysis)
            
            # 更新状态
            self.status_label.config(
                text=f"解析完成 {'(使用缓存)' if from_cache else '(已缓存)'}",
                fg='#27ae60'
            )
            self.status_bar.config(text=f"解析完成 | 题目ID: {question_id} | {'缓存' if from_cache else '新建'}")
        else:
            error_msg = result.get('error', '未知错误')
            self.result_text.delete(1.0, tk.END)
            self.result_text.insert(tk.END, f"❌ 解析失败\n\n错误信息：{error_msg}")
            self.status_label.config(text="解析失败", fg='#e74c3c')
    
    def _show_error(self, error_msg):
        """显示错误"""
        self.analyze_button.config(state=tk.NORMAL)
        self.result_text.delete(1.0, tk.END)
        
        # 清理错误信息，移除可能的日志信息
        clean_error = error_msg
        # 移除服务启动相关的日志信息
        if "🚀 服务启动中" in clean_error or "📍 API地址" in clean_error or "📖 API文档" in clean_error:
            clean_error = "API服务可能正在重启，请稍后重试"
        # 移除其他可能的日志信息
        lines = clean_error.split('\n')
        filtered_lines = [line for line in lines if not any(x in line for x in ['🚀', '📍', '📖', 'Debugger', 'Detected change', 'Restarting'])]
        clean_error = '\n'.join(filtered_lines) if filtered_lines else clean_error
        
        self.result_text.insert(tk.END, f"❌ 错误\n\n{clean_error}\n\n")
        self.result_text.insert(tk.END, "提示：\n")
        self.result_text.insert(tk.END, "1. 确保API服务已启动：python app.py\n")
        self.result_text.insert(tk.END, "2. 检查图片格式是否正确\n")
        self.result_text.insert(tk.END, "3. 查看API服务终端了解详细错误")
        self.status_label.config(text="解析失败", fg='#e74c3c')
        self.status_bar.config(text="解析失败 | 请检查错误信息")
        messagebox.showerror("错误", error_msg)


def main():
    """主函数"""
    # 检查API服务是否运行
    try:
        response = requests.get("http://localhost:5000/api/stats", timeout=2)
        if not response.status_code == 200:
            messagebox.showwarning(
                "警告",
                "API服务未运行！\n\n请先启动服务：\npython app.py"
            )
    except:
        messagebox.showwarning(
            "警告",
            "无法连接到API服务！\n\n请先启动服务：\npython app.py\n\n点击确定继续（可能无法使用）"
        )
    
    # 创建窗口
    root = TkinterDnD.Tk()
    app = GongkaoApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

