# check_versions.js

用途：在 GitHub Pull Request 中检查仓库内的 `package.json` 文件版本是否小于仓库中最新的 Release 版本。

使用方法：

- 工作流（已添加）会在 `pull_request` 事件运行该脚本，默认仅发出警告（不会失败 PR）。
- 如果希望在发现过期版本时让 CI 失败，请在工作流中设置环境变量 `FAIL_ON_OUTDATED: 'true'`。

配置示例（workflow）：

  - name: Run package version check
    env:
      GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      FAIL_ON_OUTDATED: 'false' # 改成 'true' 则发现过期版本会使流程失败
    run: node .github/scripts/check_versions.js

注意事项：
- 脚本通过 GitHub Releases 的 `releases/latest` 接口读取最新发布版本，标签会剥离前导 `v` 后比较语义版本号（仅按 `major.minor.patch` 比较）。
- 脚本会递归扫描仓库中的 `package.json` 文件（跳过 `node_modules`、`.git`、`dist` 目录）。
- 如需更复杂的版本比较（预发布、build metadata），可改用 `semver` 包并把项目依赖加入 workflow。 
