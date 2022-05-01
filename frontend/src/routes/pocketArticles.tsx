import React from "react";
import { useSearchParams } from "react-router-dom";
import PocketArticlesTable from "../components/PocketArticlesTable";
import { useCountPocketArticles, useReadTags } from "../api";
import { Select } from "antd";

const { Option } = Select;

const PocketArticles = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const { data: countArticles, status: countArticlesStatus } =
    useCountPocketArticles({
      query: { select: (d) => d.data },
    });
  console.log(countArticles);

  const ignoreTags = ["feedly", "ifttt", "saved for later"];
  const { data: tags, status: tagsStatus } = useReadTags(
    { is_pocket_tag: true },
    { query: { select: (d) => d.data } }
  );
  tags?.sort((a, b) => {
    if (
      typeof a.num_pocket_articles !== "undefined" &&
      typeof b.num_pocket_articles !== "undefined"
    ) {
      return b.num_pocket_articles - a.num_pocket_articles;
    } else if (typeof a.num_pocket_articles === "undefined") {
      return 1;
    } else {
      return -1;
    }
  });
  console.log(tags);
  const filteredTags = tags?.filter((tag) => !ignoreTags.includes(tag.name));
  const options = filteredTags?.map((tag) => (
    <Option key={tag.name}>
      {tag.name} ({tag.num_pocket_articles})
    </Option>
  ));

  return (
    <main>
      <p>Number of articles in the database: {countArticles}</p>
      {tagsStatus === "success" && (
        <Select
          mode="tags"
          style={{ width: "100%" }}
          placeholder="Tag Filter"
          onChange={(value: string[]) => {
            setSearchParams({ tags: value.join(",") });
          }}
        >
          {options}
        </Select>
      )}
      <PocketArticlesTable />
    </main>
  );
};

export default PocketArticles;
