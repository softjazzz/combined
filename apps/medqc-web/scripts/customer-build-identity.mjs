// 客户构建的编译常量与制品元数据必须来自同一份输入。
export function customerBuildIdentityPlugin(env = process.env) {
  const buildId = String(env.VITE_MEDQC_BUILD_ID || '').trim()
  const gitCommit = String(env.VITE_MEDQC_GIT_COMMIT || '').trim()
  const identity =
    buildId && /^[0-9a-f]{40}$/i.test(gitCommit)
      ? { build_id: buildId, git_commit: gitCommit }
      : { build_id: '', git_commit: '' }

  return {
    name: 'medqc-customer-build-identity',
    config() {
      return {
        define: {
          'import.meta.env.VITE_MEDQC_BUILD_ID': JSON.stringify(identity.build_id),
          'import.meta.env.VITE_MEDQC_GIT_COMMIT': JSON.stringify(identity.git_commit),
        },
      }
    },
    generateBundle() {
      this.emitFile({
        type: 'asset',
        fileName: 'build-info.json',
        source: `${JSON.stringify(identity)}\n`,
      })
    },
  }
}
