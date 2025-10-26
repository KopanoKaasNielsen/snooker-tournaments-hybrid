export interface UserProfile {
  id: string;
  username: string;
  email: string;
  favouriteCue?: string;
  ranking: number;
  walletBalance: number;
  avatarUrl?: string;
}
