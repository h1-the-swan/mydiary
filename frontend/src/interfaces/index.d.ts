export interface IPocketArticle {
  id: string;
  given_title: string;
  resolved_title: string;
  url: string;
  favorite: boolean;
  status: number; // todo make this an enum
  // todo look into dates
  time_added: string;
  time_updated: string;
  time_read: string;
  top_image_url: string;
}
