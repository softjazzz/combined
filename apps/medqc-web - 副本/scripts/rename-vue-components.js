#!/usr/bin/env tsx
"use strict";
/**
 * Vue组件重命名脚本
 *
 * 此脚本用于批量重命名Vue组件文件，使其符合命名规范
 * 规范：组件名应以View或Component结尾
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.VueComponentRenamer = void 0;
const fs_1 = require("fs");
const path_1 = require("path");
class VueComponentRenamer {
    constructor(projectRoot) {
        this.renameMappings = [];
        this.projectRoot = projectRoot;
    }
    /**
     * 执行重命名操作
     */
    async renameComponents() {
        console.log('🔄 开始Vue组件重命名...\n');
        // 1. 扫描所有Vue文件并生成重命名映射
        this.scanVueFiles();
        // 2. 显示重命名计划
        this.showRenameplan();
        // 3. 执行文件重命名
        this.executeFileRenames();
        // 4. 更新所有引用
        this.updateReferences();
        console.log('\n✅ Vue组件重命名完成！');
    }
    /**
     * 扫描Vue文件
     */
    scanVueFiles() {
        const vueFiles = this.findVueFiles('src');
        for (const filePath of vueFiles) {
            const fileName = (0, path_1.basename)(filePath, '.vue');
            const dir = (0, path_1.dirname)(filePath);
            // 跳过已经符合规范的文件
            if (this.isValidComponentName(fileName)) {
                continue;
            }
            const newName = this.generateNewName(fileName, dir);
            const newPath = (0, path_1.join)(dir, `${newName}.vue`);
            this.renameMappings.push({
                oldPath: filePath,
                newPath,
                oldName: fileName,
                newName
            });
        }
    }
    /**
     * 检查组件名是否符合规范
     */
    isValidComponentName(name) {
        return /^[A-Z][a-zA-Z]*(?:View|Component)$/.test(name);
    }
    /**
     * 生成新的组件名
     */
    generateNewName(oldName, dir) {
        // 根据目录位置决定后缀
        if (dir.includes('/views/')) {
            return oldName.endsWith('View') ? oldName : `${oldName}View`;
        }
        else if (dir.includes('/components/')) {
            return oldName.endsWith('Component') ? oldName : `${oldName}Component`;
        }
        else {
            // 默认使用Component后缀
            return oldName.endsWith('Component') ? oldName : `${oldName}Component`;
        }
    }
    /**
     * 显示重命名计划
     */
    showRenameplan() {
        if (this.renameMappings.length === 0) {
            console.log('✅ 所有Vue组件名称已符合规范！');
            return;
        }
        console.log(`📋 重命名计划 (${this.renameMappings.length} 个文件):\n`);
        for (const mapping of this.renameMappings) {
            const relativePath = mapping.oldPath.replace(this.projectRoot + '/', '');
            console.log(`  ${mapping.oldName} → ${mapping.newName}`);
            console.log(`    ${relativePath}`);
        }
        console.log();
    }
    /**
     * 执行文件重命名
     */
    executeFileRenames() {
        console.log('📁 重命名文件...');
        for (const mapping of this.renameMappings) {
            try {
                (0, fs_1.renameSync)(mapping.oldPath, mapping.newPath);
                console.log(`  ✅ ${mapping.oldName} → ${mapping.newName}`);
            }
            catch (error) {
                console.error(`  ❌ 重命名失败: ${mapping.oldName} - ${error}`);
            }
        }
    }
    /**
     * 更新所有引用
     */
    updateReferences() {
        console.log('\n🔗 更新组件引用...');
        // 需要更新引用的文件类型
        const fileExtensions = ['.vue', '.ts', '.js'];
        for (const ext of fileExtensions) {
            const files = this.findFiles('src', ext);
            for (const file of files) {
                this.updateFileReferences(file);
            }
        }
    }
    /**
     * 更新单个文件中的引用
     */
    updateFileReferences(filePath) {
        try {
            let content = (0, fs_1.readFileSync)(filePath, 'utf-8');
            let hasChanges = false;
            for (const mapping of this.renameMappings) {
                // 更新import语句
                const importRegex = new RegExp(`(import\\s+\\w+\\s+from\\s+['"].*/)${mapping.oldName}(['"])`, 'g');
                if (importRegex.test(content)) {
                    content = content.replace(importRegex, `$1${mapping.newName}$2`);
                    hasChanges = true;
                }
                // 更新组件注册
                const componentRegex = new RegExp(`\\b${mapping.oldName}\\b`, 'g');
                if (componentRegex.test(content)) {
                    content = content.replace(componentRegex, mapping.newName);
                    hasChanges = true;
                }
            }
            if (hasChanges) {
                (0, fs_1.writeFileSync)(filePath, content, 'utf-8');
                const relativePath = filePath.replace(this.projectRoot + '/', '');
                console.log(`  ✅ 更新引用: ${relativePath}`);
            }
        }
        catch (error) {
            console.error(`  ❌ 更新引用失败: ${filePath} - ${error}`);
        }
    }
    /**
     * 查找Vue文件
     */
    findVueFiles(dir) {
        return this.findFiles(dir, '.vue');
    }
    /**
     * 查找指定扩展名的文件
     */
    findFiles(dir, extension) {
        const files = [];
        const fullDir = (0, path_1.join)(this.projectRoot, dir);
        try {
            const items = (0, fs_1.readdirSync)(fullDir);
            for (const item of items) {
                const fullPath = (0, path_1.join)(fullDir, item);
                const stat = (0, fs_1.statSync)(fullPath);
                if (stat.isDirectory()) {
                    // 递归查找子目录
                    const subFiles = this.findFiles((0, path_1.join)(dir, item), extension);
                    files.push(...subFiles);
                }
                else if ((0, path_1.extname)(item) === extension) {
                    files.push(fullPath);
                }
            }
        }
        catch (error) {
            // 目录不存在或无法访问
        }
        return files;
    }
}
exports.VueComponentRenamer = VueComponentRenamer;
/**
 * 主函数
 */
async function main() {
    const projectRoot = process.cwd();
    const renamer = new VueComponentRenamer(projectRoot);
    try {
        await renamer.renameComponents();
    }
    catch (error) {
        console.error('❌ 重命名过程中发生错误:', error);
        process.exit(1);
    }
}
// 如果直接运行此脚本
if (import.meta.url === `file://${process.argv[1]}`) {
    main();
}
