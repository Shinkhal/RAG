import type { ReactNode } from "react";

interface FeatureCardProps {
  icon: ReactNode;
  title: string;
  description: string;
  tone?: "green" | "blue" | "amber" | "rose";
}

export function FeatureCard({ icon, title, description, tone = "green" }: FeatureCardProps) {
  return (
    <div className="feature-card">
      <span className={`feature-card__icon feature-card__icon--${tone}`} aria-hidden="true">
        {icon}
      </span>
      <h3 className="feature-card__title">{title}</h3>
      <p className="feature-card__desc">{description}</p>
    </div>
  );
}
