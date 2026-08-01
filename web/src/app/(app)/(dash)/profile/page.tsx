import { api } from "@/lib/api";
import dashStyles from "../dash.module.css";
import { TopBar } from "../TopBar";
import { ProfileTabs } from "./ProfileTabs";

export const metadata = { title: "Profile — mcpfor.work" };

export default async function ProfilePage() {
  const profile = await api.getProfile();
  return (
    <>
      <TopBar title="Profile" />
      <div className={dashStyles.content}>
        <ProfileTabs profile={profile} />
      </div>
    </>
  );
}
