interface Props {
  title?: string;
  message: string;
}

export default function ErrorBanner({ title = "Something went wrong", message }: Props) {
  return (
    <div className="rounded-md border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-900">
      <div className="font-semibold">{title}</div>
      <div className="mt-0.5 text-rose-800">{message}</div>
    </div>
  );
}
