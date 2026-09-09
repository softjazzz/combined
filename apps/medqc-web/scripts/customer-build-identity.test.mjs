import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import { customerBuildIdentityPlugin } from './customer-build-identity.mjs'

test('编译常量与构建元数据使用同一标识', () => {
  const identity = { build_id: 'medqc-web-customer-test', git_commit: 'a'.repeat(40) }
  const env = { VITE_MEDQC_BUILD_ID: identity.build_id, VITE_MEDQC_GIT_COMMIT: identity.git_commit }
  const plugin = customerBuildIdentityPlugin(env)
  env.VITE_MEDQC_BUILD_ID = 'changed-after-config'
  assert.deepEqual(plugin.config().define, {
    'import.meta.env.VITE_MEDQC_BUILD_ID': JSON.stringify(identity.build_id),
    'import.meta.env.VITE_MEDQC_GIT_COMMIT': JSON.stringify(identity.git_commit),
  })
  const assets = []
  plugin.generateBundle.call({ emitFile: (asset) => assets.push(asset) })
  assert.equal(assets[0].fileName, 'build-info.json')
  assert.deepEqual(JSON.parse(assets[0].source), identity)
})

test('打包先拒绝旧制品并校验本次构建标识后才复制', () => {
  const script = readFileSync(new URL('./package-customer-release.ps1', import.meta.url), 'utf8')
  assert.match(script, /if \(\$SkipBuild\)\s*\{\s*throw "-SkipBuild is not supported/)
  assert.match(script, /--config vite\.customer\.config\.mjs/)
  assert.match(script, /\$env:VITE_MEDQC_BUILD_ID = \$releaseName/)
  assert.match(script, /\$env:VITE_MEDQC_GIT_COMMIT = \$verifiedSourceCommit/)
  assert.match(
    script,
    /finally\s*\{\s*\$env:VITE_MEDQC_BUILD_ID = \$previousBuildId\s*\$env:VITE_MEDQC_GIT_COMMIT = \$previousGitCommit/,
  )
  assert.match(script, /\$frontendBuildInfo\.build_id -cne \$releaseName/)
  assert.match(script, /\$frontendBuildInfo\.git_commit -cne \$verifiedSourceCommit/)
  assert.ok(
    script.indexOf('$frontendBuildInfo.build_id -cne') <
      script.indexOf('Write-Step "Copy frontend build artifacts"'),
  )
  assert.match(
    script,
    /if \(-not \$AllowDirty\) \{[\s\S]*--runtime-build-output[\s\S]*--build-id \$releaseName/,
  )
})

test('缺标识或无效提交号不会伪造正式构建标识', () => {
  for (const env of [
    {},
    { VITE_MEDQC_BUILD_ID: 'release' },
    { VITE_MEDQC_BUILD_ID: 'release', VITE_MEDQC_GIT_COMMIT: 'dirty' },
  ]) {
    const plugin = customerBuildIdentityPlugin(env)
    assert.equal(plugin.config().define['import.meta.env.VITE_MEDQC_BUILD_ID'], '""')
    plugin.generateBundle.call({
      emitFile(asset) {
        assert.deepEqual(JSON.parse(asset.source), { build_id: '', git_commit: '' })
      },
    })
  }
})
