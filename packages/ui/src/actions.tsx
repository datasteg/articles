import type { ButtonHTMLAttributes, ReactNode } from 'react';
import { cx, Icon, ICONS, type IconName } from './util';

export interface ButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'lang'> {
  /** primary = accent fill (one per view) · secondary = outlined (default) · quiet = text only · deep = on deep blocks only */
  variant?: 'primary' | 'secondary' | 'quiet' | 'deep';
  size?: 'md' | 'sm';
  href?: string;
  icon?: IconName;
  children?: ReactNode;
}

export function Button({ variant = 'secondary', size, className, children, href, icon, ...rest }: ButtonProps) {
  const cls = cx('gl-btn', 'gl-btn--' + variant, size === 'sm' && 'gl-btn--sm', className);
  const kids = (
    <>
      {icon && ICONS[icon] ? <Icon name={icon} /> : null}
      {children}
    </>
  );
  if (href) {
    return <a className={cls} href={href} aria-label={rest['aria-label']} title={rest.title}>{kids}</a>;
  }
  return <button type="button" className={cls} {...rest}>{kids}</button>;
}
