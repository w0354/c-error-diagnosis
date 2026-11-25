#include <stdio.h>
int main(void)
{
FILE *fp = fopen("data.txt", "w");
fprintf(fp, "%d\n", 100);
fclose(fp);
return 0;
}
