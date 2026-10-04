// components/ModeToggle.tsx
"use client"
import { useTheme } from 'next-themes';
import { MoonIcon, SunIcon } from '@radix-ui/react-icons';

const ModeToggle: React.FC = () => {
  const { theme, setTheme } = useTheme();

  return (
    <button
      onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
      className="rounded-full p-2 bg-transparent dark:bg-tranasparent"
    >
      {theme === 'dark' ? <SunIcon className="h-6 w-6" /> : <MoonIcon className="h-6 w-6" />}
    </button>
  );
};

export default ModeToggle;