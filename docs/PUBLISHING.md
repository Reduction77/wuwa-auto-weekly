# 使用 GitHub Desktop 上传

本项目文件已整理，但尚未创建远端仓库或上传。发布操作由你完成。

相关操作可参考 [GitHub Desktop 官方说明](https://docs.github.com/en/desktop/adding-and-cloning-repositories/adding-an-existing-project-to-github-using-github-desktop)。

## 首次发布

1. 在 GitHub Desktop 选择 **File → Add local repository**，选择本项目目录。
2. 如果提示当前不是 Git 仓库，点击提示中的 **create a repository here**。确认生成的仓库路径就是项目根目录，不要额外套一层同名文件夹。
3. 使用现有 `README.md`、`.gitignore` 和 `LICENSE`，无需由 Desktop 重新生成。
4. 查看 **Changes**：应只有源代码、默认配置、测试、工具、文档、依赖列表和启动脚本。
5. 确认没有 `data/`、`.deps/`、`.venv/`、数据库、游戏截图、账号信息及下载的参考资料。
6. 填写首次提交说明，例如 `Initial public release`，点击 **Commit to main**。
7. 点击 **Publish repository**，填写仓库名和描述。希望公开时取消 **Keep this code private**，再发布。
8. 打开 GitHub 页面，检查 README 中的界面图、文档链接和 MIT 许可证是否正常显示。

推荐仓库名：`weekly-garden-assistant`。可用简介：`鸣潮国服周常乐园多账号桌面助手，支持后台窗口操作与本地运行记录。`

## 上传范围

`.gitignore` 已排除本地数据、依赖目录、虚拟环境、缓存、构建产物和常见编辑器文件。它只对未跟踪文件生效；如果你曾手动提交这些目录，仍需先从版本跟踪中移除。

README 的界面截图使用虚构演示账号。MIT 适用于原创代码，游戏名称及识别素材的权利说明见 README。

## 发布后自检

建议从 GitHub 克隆到另一个空目录，执行 `setup.cmd` 后启动。这样可检查安装是否意外依赖你本机的 `.deps` 或 `data`。首次公开版建议注明“实机适配中”，不要标注为所有账号均可稳定无人值守。
