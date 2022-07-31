import React from "react";
import { Card } from "antd";
import { PerformSongRead } from "../api";

interface IPerformSongCard {
  performSong: PerformSongRead;
  imageUrl?: string;
}

const PerformSongCard: React.FC<IPerformSongCard> = (props) => {
  const { performSong, imageUrl } = props;
  return (
    <Card
      hoverable
      style={{ width: 240 }}
      cover={<img alt="album cover" src={imageUrl} />}
    >
      <p>{performSong.name}</p>
      <p>{performSong.artist_name}</p>
      {performSong.key && <p>Key: {performSong.key}</p>}
      {performSong.capo != null && <p>Capo: {performSong.capo}</p>}
      {performSong.notes && <p>Notes: {performSong.notes}</p>}
      {performSong.perform_url && <p>Perform URL: {performSong.perform_url}</p>}
    </Card>
  );
};

export default PerformSongCard;
