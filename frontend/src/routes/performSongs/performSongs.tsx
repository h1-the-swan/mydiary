import React, { useEffect } from "react";
import {
  PerformSongRead,
  usePerformSongCount,
  useReadPerformSongsList,
} from "../../api";
import { Button, Table, TableColumnType } from "antd";
import { Link, useNavigate } from "react-router-dom";
import moment from "moment";
import ButtonRandomPerformSong from "../../components/ButtonRandomPerformSong";

interface PerformSongTableProps {
  performSongs?: PerformSongRead[];
}

function PerformSongTable(props: PerformSongTableProps) {
  const { performSongs } = props;
  if (!performSongs) return null;
  const columns: TableColumnType<PerformSongRead>[] = [
    {
      title: "id",
      dataIndex: "id",
      key: "id",
      render: (value: number) => {
        return <Link to={`/performSongs/song?id=${value}`}>{value}</Link>;
      },
      sorter: (a, b) => a.id - b.id,
    },
    {
      title: "Name",
      dataIndex: "name",
      // key: "name",
      sorter: (a, b) => a.name.localeCompare(b.name),
    },
    {
      title: "Artist",
      dataIndex: "artist_name",
      key: "artist",
      sorter: (a, b) => {
        if (!a.artist_name && !b.artist_name) {
          return 0;
        } else if (!a.artist_name) {
          return 1;
        } else if (!b.artist_name) {
          return -1;
        } else {
          return a.artist_name.localeCompare(b.artist_name);
        }
      },
    },
    {
      title: "Learned",
      dataIndex: "learned",
      key: "learned",
      render: (value: boolean) => Number(value),
      sorter: (a, b) => Number(a.learned) - Number(b.learned),
      filters: [
        {
          text: "Learned",
          value: true,
        },
        {
          text: "Not Learned",
          value: false,
        },
      ],
      onFilter: (value, record: PerformSongRead) => record.learned === value,
    },
    {
      title: "Spotify ID",
      dataIndex: "spotify_id",
      key: "spotify_id",
      render: (spotify_id: string) => {
        const uri = `spotify:track:${spotify_id}`;
        return (
          <a href={uri} target="_blank" rel="noreferrer">
            {spotify_id}
          </a>
        );
      },
    },
    {
      title: "Key",
      dataIndex: "key",
      key: "key",
      sorter: (a, b) => {
        if (!a.key && !b.key) {
          return 0;
        } else if (!a.key) {
          return 1;
        } else if (!b.key) {
          return -1;
        } else {
          return a.key.localeCompare(b.key);
        }
      },
    },
    {
      title: "Capo",
      dataIndex: "capo",
      key: "capo",
      sorter: (a, b) => {
        if (a.capo == null && b.capo == null) {
          return 0;
        } else if (a.capo == null) {
          return 1;
        } else if (b.capo == null) {
          return -1;
        } else {
          return a.capo - b.capo;
        }
      },
    },
    {
      title: "Created At",
      dataIndex: "created_at",
      key: "created_at",
      render: (value: string) => {
        if (value != null) {
          const dt = moment(value + "Z");
          return dt.format("MMMM D YYYY");
        }
        return "";
      },
      sorter: (a, b) => {
        if (a.created_at == null && b.created_at == null) {
          return 0;
        } else if (a.created_at == null) {
          return 1;
        } else if (b.created_at == null) {
          return -1;
        } else {
          return (
            new Date(a.created_at + "Z").getTime() -
            new Date(b.created_at + "Z").getTime()
          );
        }
      },
    },
  ];
  return (
    <Table
      dataSource={performSongs}
      columns={columns}
      pagination={{ pageSize: 100 }}
      rowKey="id"
    />
  );
}

const PerformSongs = () => {
  // const { data: spotifyHistoryCount } = useSpotifyHistoryCount({
  //   query: { select: (d) => d.data },
  // });
  const { data: performSongsCount } = usePerformSongCount({
    query: { select: (d) => d.data },
  });
  const { data: performSongs, isLoading } = useReadPerformSongsList(
    { limit: 5000 },
    {
      query: {
        select: (d) => d.data,
      },
    }
  );
  useEffect(() => console.log(performSongs), [performSongs]);

  return (
    <main>
      {performSongsCount && (
        <p>There are {performSongsCount} items in the database.</p>
      )}
      {isLoading ? (
        <span>Loading...</span>
      ) : (
        performSongs && (
          <>
            <ButtonRandomPerformSong performSongs={performSongs} />
            <PerformSongTable performSongs={performSongs} />
          </>
        )
      )}
    </main>
  );
};

export { PerformSongs };
