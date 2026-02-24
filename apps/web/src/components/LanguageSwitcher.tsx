import { useLocale, useTranslations } from 'next-intl';
import { usePathname, useRouter } from '@/i18n/navigation';
import { useTransition } from 'react';
import { Languages } from 'lucide-react';

interface LanguageSwitcherProps {
    isCollapsed?: boolean;
}

export default function LanguageSwitcher({ isCollapsed = false }: LanguageSwitcherProps) {
    const t = useTranslations('Navigation');
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
            className={`flex items-center gap-3 w-full rounded-lg px-3 py-3 transition-colors text-stone-500 hover:bg-stone-100 hover:text-stone-900 ${isPending ? 'opacity-50 cursor-not-allowed' : ''
                }`}
            title={isCollapsed ? (locale === 'en' ? 'Switch to Chinese' : '切换为英文') : undefined}
        >
            <Languages size={24} className="text-stone-500" />
            {!isCollapsed && (
                <span className="font-medium whitespace-nowrap overflow-hidden">
                    {locale === 'en' ? 'English' : '中文'}
                </span>
            )}
        </button>
    );
}
