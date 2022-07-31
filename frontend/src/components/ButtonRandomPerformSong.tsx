import React, { useState } from "react";
import { Button } from "antd";
import { Link, useNavigate } from "react-router-dom";
import { PerformSongRead, useReadPerformSongsList } from "../api";

interface IButtonRandomPerformSong {
  performSongs?: PerformSongRead[];
  currentId?: number;
}

const ButtonRandomPerformSong: React.FC<IButtonRandomPerformSong> = (props) => {
  const [performSongs, setPerformSongs] = useState(props.performSongs);
  useReadPerformSongsList(
    { limit: 5000 },
    {
      query: {
        select: (d) => d.data,
        enabled: performSongs == null,
        onSuccess: (data) => setPerformSongs(data),
      },
    }
  );
  let navigate = useNavigate();
  function randomPerformSong(performSongs: PerformSongRead[]) {
    const learnedSongs = performSongs.filter((song) => song.learned === true);
    function getRandomSong() {
      return learnedSongs[Math.floor(Math.random() * learnedSongs.length)];
    }
    let randomSong = getRandomSong();
    // make sure the song isn't the same as the current one
    while (randomSong.id === props.currentId) {
      randomSong = getRandomSong();
    }
    return randomSong;
  }
  return performSongs ? (
    <Button
      onClick={() => {
        const s = randomPerformSong(performSongs);
        console.log(s);
        navigate(`/performSongs/song?id=${s.id}`);
      }}
    >
      Random Song
    </Button>
  ) : null;
};

export default ButtonRandomPerformSong;
