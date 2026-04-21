# Git 主要操作命令整理

这份笔记整理 Git 日常开发中最常用的命令，适合作为快速查询表。

## 1. 查看状态

查看当前仓库状态：

```bash
git status
```

查看当前分支：

```bash
git branch
```

查看提交历史：

```bash
git log
```

简洁查看提交历史：

```bash
git log --oneline
```

查看远程仓库地址：

```bash
git remote -v
```

## 2. 初始化仓库

在当前目录初始化 Git 仓库：

```bash
git init
```

设置默认分支为 main：

```bash
git branch -M main
```

## 3. 连接远程仓库

添加远程仓库：

```bash
git remote add origin https://github.com/用户名/仓库名.git
```

修改远程仓库地址：

```bash
git remote set-url origin https://github.com/用户名/新仓库名.git
```

删除远程仓库关联：

```bash
git remote remove origin
```

## 4. 添加和提交修改

添加指定文件到暂存区：

```bash
git add 文件名
```

添加所有修改到暂存区：

```bash
git add .
```

提交修改：

```bash
git commit -m "提交说明"
```

示例：

```bash
git add .
git commit -m "新增 hello world 文件"
```

## 5. 推送代码到远程仓库

第一次推送 main 分支：

```bash
git push -u origin main
```

之后正常推送：

```bash
git push
```

推送指定分支：

```bash
git push origin 分支名
```

## 6. 拉取远程代码

拉取远程最新代码并合并：

```bash
git pull
```

从指定远程分支拉取：

```bash
git pull origin main
```

只获取远程更新，不自动合并：

```bash
git fetch
```

## 7. 克隆仓库

从 GitHub 克隆仓库：

```bash
git clone https://github.com/用户名/仓库名.git
```

克隆到指定目录：

```bash
git clone https://github.com/用户名/仓库名.git 目录名
```

## 8. 分支操作

查看本地分支：

```bash
git branch
```

查看所有分支，包括远程分支：

```bash
git branch -a
```

创建新分支：

```bash
git branch 分支名
```

切换分支：

```bash
git switch 分支名
```

创建并切换到新分支：

```bash
git switch -c 分支名
```

合并某个分支到当前分支：

```bash
git merge 分支名
```

删除本地分支：

```bash
git branch -d 分支名
```

强制删除本地分支：

```bash
git branch -D 分支名
```

删除远程分支：

```bash
git push origin --delete 分支名
```

## 9. 查看修改内容

查看工作区未暂存的修改：

```bash
git diff
```

查看暂存区的修改：

```bash
git diff --cached
```

查看某次提交的内容：

```bash
git show 提交ID
```

## 10. 撤销修改

撤销某个文件在工作区的修改：

```bash
git restore 文件名
```

取消暂存某个文件：

```bash
git restore --staged 文件名
```

修改最近一次提交说明：

```bash
git commit --amend -m "新的提交说明"
```

回退到上一个提交，但保留文件修改：

```bash
git reset --soft HEAD~1
```

回退到上一个提交，并取消暂存，但保留文件修改：

```bash
git reset --mixed HEAD~1
```

危险操作：回退到上一个提交，并丢弃文件修改：

```bash
git reset --hard HEAD~1
```

## 11. 标签操作

查看标签：

```bash
git tag
```

创建标签：

```bash
git tag v1.0.0
```

推送标签：

```bash
git push origin v1.0.0
```

推送所有标签：

```bash
git push origin --tags
```

删除本地标签：

```bash
git tag -d v1.0.0
```

删除远程标签：

```bash
git push origin --delete v1.0.0
```

## 12. 常见完整流程

### 第一次把本地项目提交到 GitHub

```bash
git init
git branch -M main
git remote add origin https://github.com/用户名/仓库名.git
git add .
git commit -m "Initial commit"
git push -u origin main
```

### 日常提交代码

```bash
git status
git add .
git commit -m "提交说明"
git push
```

### 开发新功能

```bash
git switch -c feature/功能名
git add .
git commit -m "实现某个功能"
git push -u origin feature/功能名
```

### 拉取别人提交的最新代码

```bash
git pull
```

如果担心自动合并，可以先执行：

```bash
git fetch
git status
```

## 13. 提交说明建议

提交说明建议写清楚“这次修改做了什么”。

常见示例：

```text
新增登录页面
修复按钮点击无响应问题
更新 README 文档
优化数据加载逻辑
删除无用文件
```

英文项目中常见写法：

```text
Add login page
Fix button click handler
Update README
Improve data loading
Remove unused files
```

## 14. 常见问题

### 提示 remote origin already exists

说明已经存在 origin 远程仓库。可以查看：

```bash
git remote -v
```

如果要换地址：

```bash
git remote set-url origin https://github.com/用户名/仓库名.git
```

### 提示 nothing to commit

说明当前没有新的修改需要提交。可以查看：

```bash
git status
```

### 推送失败，提示先 pull

说明远程仓库有本地没有的提交，先拉取：

```bash
git pull
```

解决冲突后再提交和推送：

```bash
git add .
git commit -m "解决合并冲突"
git push
```

## 15. 推荐记住的核心命令

日常最常用的是这几个：

```bash
git status
git add .
git commit -m "提交说明"
git pull
git push
git branch
git switch 分支名
git log --oneline
git remote -v
```
