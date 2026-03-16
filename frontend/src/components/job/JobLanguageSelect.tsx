import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

type JobLanguage = "en" | "zh";

type JobLanguageSelectProps = {
  value: JobLanguage;
  onValueChange: (value: string) => void;
  hasChinese: boolean;
  triggerClassName?: string;
};

export function JobLanguageSelect({
  value,
  onValueChange,
  hasChinese,
  triggerClassName,
}: JobLanguageSelectProps) {
  return (
    <Select value={value} onValueChange={onValueChange}>
      <SelectTrigger className={triggerClassName ?? "h-9 w-[140px]"}>
        <SelectValue placeholder="Language" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="en">English</SelectItem>
        <SelectItem value="zh" disabled={!hasChinese}>
          中文
        </SelectItem>
      </SelectContent>
    </Select>
  );
}
