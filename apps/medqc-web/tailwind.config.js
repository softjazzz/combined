/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{vue,js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            colors: {
                // 医疗系统主题色
                medical: {
                    50: '#f0f9ff',
                    100: '#e0f2fe',
                    200: '#bae6fd',
                    300: '#7dd3fc',
                    400: '#38bdf8',
                    500: '#0ea5e9',
                    600: '#0284c7',
                    700: '#0369a1',
                    800: '#075985',
                    900: '#0c4a6e',
                },
                // Ant Design 兼容色彩
                primary: '#1890ff',
                success: '#52c41a',
                warning: '#faad14',
                error: '#f5222d',
                info: '#1890ff',
            },
            fontFamily: {
                sans: [
                    'PingFang SC',
                    'Microsoft YaHei',
                    'SF Pro Display',
                    'Helvetica Neue',
                    'Arial',
                    'sans-serif',
                ],
            },
            spacing: {
                '18': '4.5rem',
                '88': '22rem',
            },
            animation: {
                'fade-in': 'fadeIn 0.3s ease-in-out',
                'slide-up': 'slideUp 0.3s ease-out',
                'bounce-light': 'bounceLight 1s infinite',
            },
            keyframes: {
                fadeIn: {
                    '0%': { opacity: '0' },
                    '100%': { opacity: '1' },
                },
                slideUp: {
                    '0%': { transform: 'translateY(10px)', opacity: '0' },
                    '100%': { transform: 'translateY(0)', opacity: '1' },
                },
                bounceLight: {
                    '0%, 100%': { transform: 'translateY(-5%)' },
                    '50%': { transform: 'translateY(0)' },
                },
            },
        },
    },
    plugins: [
        require('@tailwindcss/typography'),
        require('@tailwindcss/forms'),
    ],
    corePlugins: {
        // 启用基础样式，但排除可能与 Ant Design 冲突的部分
        preflight: true,
    },
    // 添加重要性前缀以确保Tailwind样式优先级
    important: true,
}
