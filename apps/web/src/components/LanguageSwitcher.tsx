import { useLocale } from 'next-intl';
import { usePathname, useRouter } from '@/i18n/navigation';
import { useTransition } from 'react';
import { Languages } from 'lucide-react';

interface LanguageSwitcherProps {
    isCollapsed?: boolean;
}

export default function LanguageSwitcher({ isCollapsed = false }: LanguageSwitcherProps) {
    const locale = useLocale();
    const router = useRouter();
    const pathname = usePathname();
    const [isPending, startTransition] = useTransition();

    const toggleLanguage = () => {
        const nextLocale = locale === 'en' ? 'zh' : 'en';
        startTransition(() => {
            router.replace(pathname, { locale: nextLocale });
        });
    };

    return (
        <button
            onClick={toggleLanguage}
            disabled={isPending}
            className={`flex items-center gap-3 2xl:gap-5 w-full rounded-lg 2xl:rounded-xl px-3 py-3 2xl:px-5 2xl:py-5 transition-colors text-stone-500 hover:bg-stone-100 hover:text-stone-900 ${isPending ? 'opacity-50 cursor-not-allowed' : ''
                }`}
            title={isCollapsed ? (locale === 'en' ? 'Switch to Chinese' : '切换为英文') : undefined}
        >
            <Languages className="w-6 h-6 2xl:w-8 2xl:h-8 text-stone-500" />
            {!isCollapsed && (
                <span className="font-medium 2xl:text-xl whitespace-nowrap overflow-hidden">
                    {locale === 'en' ? 'English' : '中文'}
                </span>
            )}
        </button>
    );
}
